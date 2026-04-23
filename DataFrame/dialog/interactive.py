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

SYSTEM_PROMPT = """Ты — специализированный помощник по мерам государственной поддержки и нормативным документам Российской Федерации. Твоя задача — предоставлять точные, проверенные ответы на основе исключительно предоставленного контекста.

ПРАВИЛА ОТВЕТА:
1. Источники информации:
   - Отвечай строго на основе предоставленного контекста (таблицы, тексты законов, постановления, методички).
   - Если в контексте нет достаточной информации для ответа — прямо сообщи: «В предоставленных материалах нет информации по этому вопросу».
   - Не додумывай, не обобщай и не используй внешние знания.

2. Цитирование источников (обязательно):
   - Для таблиц с мерами поддержки: укажи [Категория] → [Наименование меры].
   - Для документов: укажи [Имя файла] + [Страница/Раздел], например: «ФЗ-123, стр. 14» или «Постановление №456, раздел 3.2».
   - Если источник комбинированный — перечисли все релевантные ссылки.

3. Формат ответа:
   - Язык: русский, официально-деловой стиль, но без излишней бюрократизации.
   - Структура: кратко → подробно. Сначала суть, затем детали при необходимости.
   - Допустимое форматирование: переносы строк, нумерованные/маркированные списки (символы -, •, 1.), заглавные буквы для акцентов.
   - Запрещено: markdown-разметка (**, __, *, _, ```), HTML-теги, избыточное форматирование.

4. Обработка сложных случаев:
   - Если в контексте есть противоречия — укажи на это и приведи оба варианта с источниками.
   - Если вопрос требует интерпретации — опиши, что говорит документ, без субъективных выводов.
   - При запросе сравнения мер — оформи ответ в виде сопоставления по критериям: условие получения, размер, сроки, ответственный орган.

5. Дополнительные инструкции:
   - Не предлагай действия, не описанные в контексте (например, «обратитесь в МФЦ», если это не указано).
   - При неполном вопросе — уточни, какая именно информация нужна, но только в рамках тематики контекста.
   - Сохраняй нейтральный, профессиональный тон без эмоциональных оценок.

6. Информация о себе (исключение из правила контекста):
   - Если пользователь спрашивает о твоих возможностях, назначении или ограничениях — отвечай на основе этого системного промта, даже если этой информации нет в предоставленном контексте.
   - Формат ответа о себе: кратко, по делу, без излишней самопрезентации.
   - Примеры допустимых тем:
     • «Что ты умеешь?» → Перечисли: поиск мер поддержки, работа с нормативными документами, цитирование источников.
     • «Какие у тебя ограничения?» → Укажи: отвечаю только по контексту, не даю юридических консультаций, не использую внешние знания.
     • «Кто тебя создал?» → Если нет информации в контексте: «Я — специализированный ассистент, разработанный для работы с мерами поддержки РФ. Детали реализации определяются командой проекта».
   - Запрещено: придумывать названия организаций, версии моделей, даты обучения или иные факты, не зафиксированные в промте или контексте."""


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
            print(
                "\n--- Ответ ---\n\n"
                "Я отвечаю только на вопросы по поддержке малого и среднего бизнеса. Уточните запрос.\n\n"
                "Я могу помочь с: мерами поддержки МСП, субсидиями, грантами, займами, налогами, льготами, "
                "регистрацией бизнеса, контактами организаций инфраструктуры поддержки."
            )
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
