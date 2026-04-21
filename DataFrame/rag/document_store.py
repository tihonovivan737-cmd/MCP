from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path

from sqlalchemy import select

from .config import Settings
from .db import session_scope
from .models import SourceDocument

logger = logging.getLogger(__name__)


def _require_db(settings: Settings) -> str:
    if not settings.database_url:
        raise RuntimeError("Нужен DATABASE_URL для работы с source_documents")
    return settings.database_url


def put_document(settings: Settings, logical_name: str, data: bytes, mime_type: str | None = None) -> None:
    """Сохранить или обновить файл в PostgreSQL (логическое имя = ключ, напр. ТКРФ.pdf)."""
    _require_db(settings)
    if mime_type is None:
        mime_type, _ = mimetypes.guess_type(logical_name)
        mime_type = mime_type or "application/octet-stream"
    h = hashlib.sha256(data).hexdigest()
    size = len(data)
    with session_scope(settings) as session:
        row = session.get(SourceDocument, logical_name)
        if row is None:
            row = SourceDocument(
                logical_name=logical_name,
                mime_type=mime_type,
                content=data,
                sha256=h,
                size_bytes=size,
            )
            session.add(row)
        else:
            row.mime_type = mime_type
            row.content = data
            row.sha256 = h
            row.size_bytes = size
    logger.info("Загружен в PostgreSQL: %s (%s байт)", logical_name, size)


def get_document(settings: Settings, logical_name: str) -> bytes | None:
    """Прочитать файл из БД или None, если нет записи."""
    if not settings.database_url:
        return None
    with session_scope(settings) as session:
        row = session.get(SourceDocument, logical_name)
    if row is None:
        return None
    return bytes(row.content)


def list_document_names(settings: Settings) -> list[str]:
    if not settings.database_url:
        return []
    with session_scope(settings) as session:
        rows = session.execute(select(SourceDocument.logical_name).order_by(SourceDocument.logical_name)).all()
    return [r[0] for r in rows]


def put_file_path(settings: Settings, file_path: Path, logical_name: str | None = None) -> None:
    """Загрузить файл с диска: logical_name по умолчанию = basename."""
    name = logical_name or file_path.name
    data = file_path.read_bytes()
    put_document(settings, name, data)
