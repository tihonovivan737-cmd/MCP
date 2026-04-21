from __future__ import annotations

import json
import logging
import textwrap
from dataclasses import dataclass, field

from qdrant_client.http import models as qm

from .adapters import ollama_chat, retrieve_hits
from ..rag.config import Settings, load_settings
from ..rag.decision import DecisionPolicy
from ..rag.intent import classify_intent
from ..rag.logging_utils import configure_logging
from ..rag.qdrant_store import get_client

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Ты помощник по мерам поддержки и нормативным документам РФ.
Отвечай только на основе предоставленного контекста. Если в контексте нет ответа — так и скажи.
Цитируй источник: для таблицы мер — категория и наименование; для PDF — имя файла и страница.
Отвечай по-русски, структурировано и по делу."""


@dataclass
class Session:
    category_filter: str | None = None
    show_sources: bool = True
    history: list[tuple[str, str]] = field(default_factory=list)


def _format_hits(hits: list) -> tuple[str, str]:
    blocks: list[str] = []
    refs: list[str] = []
    for i, h in enumerate(hits, 1):
        pl = h.payload or {}
        st = pl.get("source_type", "")
        if st == "csv":
            ref = f"CSV: {pl.get('Категория', '')} / {str(pl.get('Наименование', ''))[:80]}"
            refs.append(ref)
        elif st == "pdf":
            ref = f"PDF: {pl.get('doc_stem', '')} стр.{pl.get('page', '')}"
            refs.append(ref)
        else:
            refs.append("источник")
        text = (pl.get("text") or "").strip()
        if not text and pl.get("row_json"):
            text = str(pl.get("row_json", ""))[:4000]
        if not text:
            text = "(нет текста в payload — выполните scripts/build_index.py заново)"
        score = getattr(h, "score", None)
        score_note = f" [релевантность: {score:.3f}]" if score is not None else ""
        blocks.append(f"--- Фрагмент {i} ({refs[-1]}){score_note} ---\n{text}")
    return "\n\n".join(blocks), "\n".join(f"- {r}" for r in refs)


def _user_message(question: str, context: str) -> str:
    return (
        f"Контекст из базы знаний:\n{context}\n\n"
        f"Вопрос: {question}\n\n"
        f"Сформулируй ответ."
    )


def _parse_filter_cmd(line: str) -> str | None:
    s = line.strip()
    if s.lower().startswith("/filter"):
        rest = s[len("/filter") :].strip()
        if "=" in rest:
            key, _, val = rest.partition("=")
            if key.strip().lower() in ("категория", "category", "к"):
                return val.strip()
        return ""
    return None


def run_interactive(settings: Settings | None = None) -> None:
    configure_logging()
    settings = settings or load_settings()
    try:
        client = get_client(settings)
    except Exception as exc:
        print(f"Не удалось подключиться к Qdrant: {exc}")
        raise SystemExit(1) from exc

    session = Session()
    print(
        "Интерактивный RAG. Команды: /help, /quit, /sources on|off, "
        "/filter категория=..., /clear",
    )
    print(f"Модель: {settings.llm_model} | Коллекция: {settings.qdrant_collection}")

    while True:
        try:
            line = input("\nВы > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nВыход.")
            break
        if not line:
            continue
        low = line.lower()
        if low in ("/quit", "/q", "exit"):
            break
        if low == "/help":
            print(
                textwrap.dedent(
                    """
                    /filter категория=Финансовая поддержка — CSV с этой категорией + все PDF
                    /clear — сбросить фильтр
                    /sources on|off — показывать источники и контекст после ответа
                    Обычный текст — поиск в Qdrant, ответ через Ollama (см. LLM_MODEL)
                    """,
                ).strip(),
            )
            continue
        if low.startswith("/sources"):
            parts = line.split()
            if len(parts) > 1 and parts[1].lower() in ("off", "0", "no"):
                session.show_sources = False
                print("Источники: выкл.")
            else:
                session.show_sources = True
                print("Источники: вкл.")
            continue
        if low == "/clear":
            session.category_filter = None
            print("Фильтр сброшен.")
            continue

        filt_val = _parse_filter_cmd(line)
        if filt_val is not None:
            if filt_val == "":
                print("Пример: /filter категория=Финансовая поддержка")
            else:
                session.category_filter = filt_val
                print(f"Фильтр категории: {session.category_filter!r}")
            continue

        question = line
        query_filter: qm.Filter | None = None
        if session.category_filter:
            query_filter = qm.Filter(
                min_should=qm.MinShould(
                    conditions=[
                        qm.FieldCondition(
                            key="Категория",
                            match=qm.MatchValue(value=session.category_filter),
                        ),
                        qm.FieldCondition(
                            key="source_type",
                            match=qm.MatchValue(value="pdf"),
                        ),
                    ],
                    min_count=1,
                ),
            )

        if not classify_intent(question, settings):
            print("\n--- Ответ ---\n\nЯ отвечаю только на вопросы по поддержке малого и среднего бизнеса. Уточните запрос.")
            continue

        hits = retrieve_hits(client, settings, question, query_filter=query_filter)

        decision = DecisionPolicy()(
            hits,
            question,
            min_score=settings.decision_min_score,
            strong_score=settings.decision_strong_score,
        )
        if decision.status != "ok":
            print(f"\n--- Ответ ---\n\n{decision.message}")
            continue

        context, refs_line = _format_hits(hits)
        user_msg = _user_message(question, context)
        answer = ollama_chat(settings, SYSTEM_PROMPT, user_msg)

        print("\n--- Ответ ---\n")
        print(answer)
        if session.show_sources:
            print("\n--- Источники ---\n")
            print(refs_line)
            print("\n--- Контекст (фрагменты) ---\n")
            print(context[:12000] + ("…" if len(context) > 12000 else ""))

        session.history.append((question, answer))


def main() -> None:
    run_interactive(load_settings())


if __name__ == "__main__":
    main()
