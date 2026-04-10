from __future__ import annotations

import logging

from ...chunking.base import Chunk
from ...chunking.csv_chunks import chunks_from_csv, chunks_from_csv_bytes
from ...chunking.pdf_chunks import chunks_from_pdf, chunks_from_pdf_bytes
from ..config import Settings

logger = logging.getLogger(__name__)


def collect_chunks(settings: Settings, *, use_pg_sources: bool | None = None) -> list[Chunk]:
    chunks: list[Chunk] = []
    if use_pg_sources is None:
        use_pg = bool(settings.database_url and settings.source_files_in_postgres)
    else:
        use_pg = bool(settings.database_url and use_pg_sources)

    if use_pg:
        from ..document_store import get_document

        csv_bytes = get_document(settings, settings.knowledge_csv_document)
        if csv_bytes:
            chunks.extend(chunks_from_csv_bytes(csv_bytes, f"postgres:{settings.knowledge_csv_document}"))
        elif settings.knowledge_csv.exists():
            logger.warning(
                "В PostgreSQL нет «%s», читаю CSV с диска: %s",
                settings.knowledge_csv_document,
                settings.knowledge_csv,
            )
            chunks.extend(chunks_from_csv(settings.knowledge_csv))
        else:
            logger.warning("CSV не найден: ни в PostgreSQL («%s»), ни файл %s", settings.knowledge_csv_document, settings.knowledge_csv)

        for pdf in settings.pdf_paths:
            name = pdf.name
            pdf_bytes = get_document(settings, name)
            if pdf_bytes:
                chunks.extend(chunks_from_pdf_bytes(pdf_bytes, name, max_chars=settings.pdf_chunk_max_chars, overlap=settings.pdf_chunk_overlap))
            elif pdf.exists():
                logger.warning("PDF «%s» не в БД, читаю с диска: %s", name, pdf)
                chunks.extend(chunks_from_pdf(pdf, max_chars=settings.pdf_chunk_max_chars, overlap=settings.pdf_chunk_overlap))
            else:
                logger.warning("PDF не найден ни в PostgreSQL («%s»), ни на диске", name)
        return chunks

    if settings.knowledge_csv.exists():
        chunks.extend(chunks_from_csv(settings.knowledge_csv))
    else:
        logger.warning("CSV не найден: %s", settings.knowledge_csv)
    for pdf in settings.pdf_paths:
        if pdf.exists():
            chunks.extend(chunks_from_pdf(pdf, max_chars=settings.pdf_chunk_max_chars, overlap=settings.pdf_chunk_overlap))
        else:
            logger.warning("PDF не найден, пропуск: %s", pdf)
    return chunks

