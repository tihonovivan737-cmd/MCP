from __future__ import annotations

import logging

from ..chunking.base import Chunk
from .config import Settings, load_settings
from .logging_utils import configure_logging
from .services.embedding_service import build_vectors
from .services.index_service import upsert_to_qdrant
from .services.manifest_service import write_manifest
from .services.source_loader import collect_chunks

logger = logging.getLogger(__name__)


def ingest(settings: Settings, *, use_pg_sources: bool | None = None) -> int:
    configure_logging()
    chunks = collect_chunks(settings, use_pg_sources=use_pg_sources)
    if not chunks:
        raise SystemExit("Нет чанков: проверьте CSV и пути к PDF.")

    if settings.database_url:
        from .postgres_store import persist_chunks_full_refresh

        uuids = persist_chunks_full_refresh(settings, chunks)
        for c, uid in zip(chunks, uuids, strict=True):
            c.chunk_id = uid

    texts = [c.text for c in chunks]
    vectors = build_vectors(texts, settings)
    ids = [c.chunk_id for c in chunks]
    if len(vectors) != len(ids):
        raise RuntimeError("Число векторов не совпало с числом чанков")
    payloads = []
    for c in chunks:
        pay = dict(c.payload)
        pay["text"] = c.text
        if settings.database_url and c.chunk_id:
            pay["postgres_id"] = c.chunk_id
        payloads.append(pay)

    upsert_to_qdrant(settings, ids, vectors, payloads)
    write_manifest(settings, chunks_total=len(chunks))
    return len(chunks)


def main() -> None:
    s = load_settings()
    n = ingest(s)
    extra = f" + PostgreSQL" if s.database_url else ""
    print(f"Индексация завершена: {n} чанков → Qdrant «{s.qdrant_collection}»{extra}")


if __name__ == "__main__":
    main()
