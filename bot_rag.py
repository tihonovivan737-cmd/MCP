"""Интеграция с RAG (DataFrame + админ-команды)."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Sequence
from pathlib import Path

HistoryTurn = tuple[str, str]

_DF_INIT_DONE = False
_DF_ERROR: str | None = None
_DF_CTX: dict[str, object] = {}


def init_dataframe_rag() -> None:
    global _DF_INIT_DONE, _DF_ERROR, _DF_CTX
    if _DF_INIT_DONE:
        return

    _DF_INIT_DONE = True
    df_root = Path(__file__).resolve().parent / "DataFrame"
    if not df_root.exists():
        _DF_ERROR = "Папка DataFrame не найдена."
        return

    df_parent = str(df_root.parent)
    if df_parent not in sys.path:
        sys.path.insert(0, df_parent)

    try:
        from DataFrame.dialog.adapters import ollama_chat as _ollama_chat  # type: ignore
        from DataFrame.dialog.adapters import ollama_chat_async as _ollama_chat_async  # type: ignore
        from DataFrame.dialog.interactive import SYSTEM_PROMPT, _format_hits  # type: ignore
        from DataFrame.rag.config import load_settings  # type: ignore
        from DataFrame.rag.embeddings import embed_texts  # type: ignore
        from DataFrame.rag.intent import classify_intent  # type: ignore
        from DataFrame.rag.qdrant_store import get_client, search  # type: ignore
    except Exception as exc:
        _DF_ERROR = (
            f"Не удалось импортировать DataFrame-модуль: {exc}. "
            "Установите зависимости: pip install -r DataFrame/requirements.txt"
        )
        return

    try:
        settings = load_settings()
        client = get_client(settings)
    except Exception as exc:
        _DF_ERROR = f"Не удалось инициализировать DataFrame: {exc}"
        return

    try:
        from DataFrame.rag.decision import DecisionPolicy  # type: ignore
        from DataFrame.rag.reranker import rerank  # type: ignore

        decision_policy = DecisionPolicy()
    except Exception:
        decision_policy = None
        rerank = None

    _DF_CTX = {
        "settings": settings,
        "client": client,
        "embed_texts": embed_texts,
        "search": search,
        "rerank": rerank,
        "_format_hits": _format_hits,
        "_ollama_chat": _ollama_chat,
        "_ollama_chat_async": _ollama_chat_async,
        "SYSTEM_PROMPT": SYSTEM_PROMPT,
        "decision_policy": decision_policy,
        "classify_intent": classify_intent,
    }


def init_dataframe_admin() -> tuple[object, object, object, object, object] | tuple[None, str]:
    df_root = Path(__file__).resolve().parent / "DataFrame"
    if not df_root.exists():
        return None, "Папка DataFrame не найдена."
    df_parent = str(df_root.parent)
    if df_parent not in sys.path:
        sys.path.insert(0, df_parent)
    try:
        from DataFrame.rag.config import load_settings  # type: ignore
        from DataFrame.rag.document_store import list_document_names, put_file_path  # type: ignore
        from DataFrame.rag.ingest_pipeline import ingest  # type: ignore
        from DataFrame.rag.postgres_store import apply_schema  # type: ignore

        return load_settings, put_file_path, list_document_names, ingest, apply_schema
    except Exception as exc:
        return None, (
            f"Не удалось импортировать функции DataFrame: {exc}. "
            "Установите зависимости: pip install -r DataFrame/requirements.txt"
        )


def run_convert_guide_trusting_postgres() -> None:
    old = os.environ.get("SOURCE_FILES_IN_POSTGRES")
    os.environ["SOURCE_FILES_IN_POSTGRES"] = "1"
    try:
        from DataFrame.ingestion.convert_guide.convert_guide import main as convert_main  # type: ignore

        convert_main()
    finally:
        if old is None:
            os.environ.pop("SOURCE_FILES_IN_POSTGRES", None)
        else:
            os.environ["SOURCE_FILES_IN_POSTGRES"] = old


def _normalize_history(history: Sequence[HistoryTurn] | None) -> list[HistoryTurn]:
    if not history:
        return []
    normalized: list[HistoryTurn] = []
    for user_text, assistant_text in history:
        user_text = (user_text or "").strip()
        assistant_text = (assistant_text or "").strip()
        if user_text or assistant_text:
            normalized.append((user_text, assistant_text))
    return normalized


def _history_slice(history: Sequence[HistoryTurn] | None, max_turns: int) -> list[HistoryTurn]:
    normalized = _normalize_history(history)
    if max_turns <= 0:
        return []
    return normalized[-max_turns:]


def _build_history_block(history: Sequence[HistoryTurn] | None, max_turns: int) -> str:
    selected = _history_slice(history, max_turns)
    if not selected:
        return ""

    lines: list[str] = []
    for user_text, assistant_text in selected:
        if user_text:
            lines.append(f"Пользователь: {user_text}")
        if assistant_text:
            lines.append(f"Ассистент: {assistant_text}")
    return "\n".join(lines)


def _build_retrieval_question(question: str, history: Sequence[HistoryTurn] | None, max_turns: int) -> str:
    selected = _history_slice(history, max_turns)
    if not selected:
        return question

    previous_questions = [user_text for user_text, _ in selected if user_text]
    if not previous_questions:
        return question

    history_text = "\n".join(f"- {item}" for item in previous_questions)
    return (
        f"История запросов пользователя:\n{history_text}\n\n"
        f"Текущий запрос:\n{question}"
    )


def _build_user_message(question: str, context: str, history: Sequence[HistoryTurn] | None, max_turns: int) -> str:
    history_block = _build_history_block(history, max_turns)
    parts: list[str] = []
    if history_block:
        parts.append(f"История диалога:\n{history_block}")
    parts.append(f"Контекст из базы знаний:\n{context}")
    parts.append(f"Текущий вопрос: {question}\n\nСформулируй ответ по существу и учти историю диалога, если она помогает.")
    return "\n\n".join(parts)


def add_source_and_reindex(file_path_raw: str, logical_name: str | None = None) -> str:
    imports = init_dataframe_admin()
    if imports[0] is None:  # type: ignore[index]
        return imports[1]  # type: ignore[index]
    load_settings, put_file_path, _list_document_names, ingest, apply_schema = imports  # type: ignore[misc]

    settings = load_settings()
    if not settings.database_url:
        return "Не задан DATABASE_URL. Сначала настройте подключение к PostgreSQL."

    path = Path(file_path_raw).expanduser().resolve()
    if not path.is_file():
        return f"Файл не найден: {path}"

    apply_schema(settings)
    logical = logical_name or path.name
    put_file_path(settings, path, logical_name=logical)

    if logical == settings.guide_xlsx_document:
        run_convert_guide_trusting_postgres()

    chunks = ingest(settings, use_pg_sources=True)
    return (
        f"Источник добавлен: {logical}\n"
        f"Переиндексация завершена: {chunks} чанков -> Qdrant «{settings.qdrant_collection}»"
    )


def reindex_from_postgres() -> str:
    imports = init_dataframe_admin()
    if imports[0] is None:  # type: ignore[index]
        return imports[1]  # type: ignore[index]
    load_settings, _put_file_path, _list_document_names, ingest, apply_schema = imports  # type: ignore[misc]

    settings = load_settings()
    if not settings.database_url:
        return "Не задан DATABASE_URL. Сначала настройте подключение к PostgreSQL."
    apply_schema(settings)
    chunks = ingest(settings, use_pg_sources=True)
    return f"Переиндексация завершена: {chunks} чанков -> Qdrant «{settings.qdrant_collection}»"


def list_sources_from_postgres() -> str:
    imports = init_dataframe_admin()
    if imports[0] is None:  # type: ignore[index]
        return imports[1]  # type: ignore[index]
    load_settings, _put_file_path, list_document_names, _ingest, _apply_schema = imports  # type: ignore[misc]

    settings = load_settings()
    if not settings.database_url:
        return "Не задан DATABASE_URL. Сначала настройте подключение к PostgreSQL."
    names = list_document_names(settings)
    if not names:
        return "В source_documents пока нет файлов."
    return "Источники в PostgreSQL:\n" + "\n".join(f"• {name}" for name in names)


def answer_from_dataframe(question: str, history: Sequence[HistoryTurn] | None = None) -> str:
    init_dataframe_rag()
    if _DF_ERROR is not None:
        return _DF_ERROR

    try:
        settings = _DF_CTX["settings"]
        client = _DF_CTX["client"]
        embed_texts = _DF_CTX["embed_texts"]
        search = _DF_CTX["search"]
        rerank = _DF_CTX["rerank"]
        _format_hits = _DF_CTX["_format_hits"]
        _ollama_chat = _DF_CTX["_ollama_chat"]
        system_prompt = _DF_CTX["SYSTEM_PROMPT"]
        decision_policy = _DF_CTX["decision_policy"]
        classify_intent = _DF_CTX["classify_intent"]

        retrieval_question = _build_retrieval_question(question, history, settings.retrieval_history_turns)
        if not classify_intent(retrieval_question, settings):
            return "Я отвечаю только на вопросы по поддержке малого и среднего бизнеса. Уточните запрос."

        fetch_limit = settings.rerank_fetch_k if settings.use_rerank else settings.retrieve_top_k
        qvec = embed_texts([retrieval_question], settings, is_query=True)[0]
        hits = search(client, settings, qvec, limit=fetch_limit, query_filter=None)

        if settings.use_rerank and rerank and hits:
            hits = rerank(retrieval_question, hits, model_name=settings.rerank_model, top_n=settings.retrieve_top_k)

        if decision_policy:
            decision = decision_policy(
                hits,
                retrieval_question,
                min_score=settings.decision_min_score,
                strong_score=settings.decision_strong_score,
            )
            if decision.status != "ok":
                return decision.message or "Не удалось обработать запрос."

        if not hits:
            return "По вашему запросу ничего не найдено в базе знаний."

        context, refs_line = _format_hits(hits)
        user_msg = _build_user_message(question, context, history, settings.chat_history_turns)
        answer = _ollama_chat(settings, system_prompt, user_msg).strip()
        if not answer:
            answer = "Не удалось сформировать ответ."
        return f"{answer}\n\nИсточники:\n{refs_line}"
    except Exception as exc:
        return f"Ошибка при обработке вопроса через DataFrame: {exc}"


async def answer_from_dataframe_async(question: str, history: Sequence[HistoryTurn] | None = None) -> str:
    init_dataframe_rag()
    if _DF_ERROR is not None:
        return _DF_ERROR

    try:
        settings = _DF_CTX["settings"]
        client = _DF_CTX["client"]
        embed_texts = _DF_CTX["embed_texts"]
        search = _DF_CTX["search"]
        rerank = _DF_CTX["rerank"]
        _format_hits = _DF_CTX["_format_hits"]
        _ollama_chat_async = _DF_CTX["_ollama_chat_async"]
        system_prompt = _DF_CTX["SYSTEM_PROMPT"]
        decision_policy = _DF_CTX["decision_policy"]
        classify_intent = _DF_CTX["classify_intent"]

        retrieval_question = _build_retrieval_question(question, history, settings.retrieval_history_turns)
        in_scope = await asyncio.to_thread(classify_intent, retrieval_question, settings)
        if not in_scope:
            return "Я отвечаю только на вопросы по поддержке малого и среднего бизнеса. Уточните запрос."

        fetch_limit = settings.rerank_fetch_k if settings.use_rerank else settings.retrieve_top_k
        vectors = await asyncio.to_thread(embed_texts, [retrieval_question], settings, is_query=True)
        hits = await asyncio.to_thread(search, client, settings, vectors[0], fetch_limit, None)

        if settings.use_rerank and rerank and hits:
            hits = await asyncio.to_thread(
                rerank,
                retrieval_question,
                hits,
                model_name=settings.rerank_model,
                top_n=settings.retrieve_top_k,
            )

        if decision_policy:
            decision = await asyncio.to_thread(
                decision_policy,
                hits,
                retrieval_question,
                min_score=settings.decision_min_score,
                strong_score=settings.decision_strong_score,
            )
            if decision.status != "ok":
                return decision.message or "Не удалось обработать запрос."

        if not hits:
            return "По вашему запросу ничего не найдено в базе знаний."

        context, refs_line = await asyncio.to_thread(_format_hits, hits)
        user_msg = _build_user_message(question, context, history, settings.chat_history_turns)
        answer = (await _ollama_chat_async(settings, system_prompt, user_msg)).strip()
        if not answer:
            answer = "Не удалось сформировать ответ."
        return f"{answer}\n\nИсточники:\n{refs_line}"
    except Exception as exc:
        return f"Ошибка при обработке вопроса через DataFrame: {exc}"
