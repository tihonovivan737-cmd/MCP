"""Блок интеграции с RAG (DataFrame + админ-команды)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

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

    if str(df_root) not in sys.path:
        sys.path.insert(0, str(df_root))

    try:
        from dialog.interactive import SYSTEM_PROMPT, _format_hits, _ollama_chat, _user_message  # type: ignore
        from rag.config import load_settings  # type: ignore
        from rag.embeddings import embed_texts  # type: ignore
        from rag.qdrant_store import get_client, search  # type: ignore
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

    _DF_CTX = {
        "settings": settings,
        "client": client,
        "embed_texts": embed_texts,
        "search": search,
        "_format_hits": _format_hits,
        "_user_message": _user_message,
        "_ollama_chat": _ollama_chat,
        "SYSTEM_PROMPT": SYSTEM_PROMPT,
    }


def init_dataframe_admin() -> tuple[object, object, object, object, object] | tuple[None, str]:
    df_root = Path(__file__).resolve().parent / "DataFrame"
    if not df_root.exists():
        return None, "Папка DataFrame не найдена."
    if str(df_root) not in sys.path:
        sys.path.insert(0, str(df_root))
    try:
        from rag.config import load_settings  # type: ignore
        from rag.document_store import list_document_names, put_file_path  # type: ignore
        from rag.ingest_pipeline import ingest  # type: ignore
        from rag.postgres_store import apply_schema  # type: ignore

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
        from ingestion.convert_guide.convert_guide import main as convert_main  # type: ignore

        convert_main()
    finally:
        if old is None:
            os.environ.pop("SOURCE_FILES_IN_POSTGRES", None)
        else:
            os.environ["SOURCE_FILES_IN_POSTGRES"] = old


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
        f"Переиндексация завершена: {chunks} чанков → Qdrant «{settings.qdrant_collection}»"
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
    return f"Переиндексация завершена: {chunks} чанков → Qdrant «{settings.qdrant_collection}»"


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


def answer_from_dataframe(question: str) -> str:
    init_dataframe_rag()
    if _DF_ERROR is not None:
        return _DF_ERROR

    try:
        settings = _DF_CTX["settings"]
        client = _DF_CTX["client"]
        embed_texts = _DF_CTX["embed_texts"]
        search = _DF_CTX["search"]
        _format_hits = _DF_CTX["_format_hits"]
        _user_message = _DF_CTX["_user_message"]
        _ollama_chat = _DF_CTX["_ollama_chat"]
        system_prompt = _DF_CTX["SYSTEM_PROMPT"]

        qvec = embed_texts([question], settings, is_query=True)[0]
        hits = search(client, settings, qvec, limit=settings.retrieve_top_k, query_filter=None)
        if not hits:
            return "По вашему запросу ничего не найдено в базе знаний."

        context, refs_line = _format_hits(hits)
        user_msg = _user_message(question, context)
        answer = _ollama_chat(settings, system_prompt, user_msg).strip()
        if not answer:
            answer = "Не удалось сформировать ответ."
        return f"{answer}\n\nИсточники:\n{refs_line}"
    except Exception as exc:
        return f"Ошибка при обработке вопроса через DataFrame: {exc}"
