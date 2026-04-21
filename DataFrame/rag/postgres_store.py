from __future__ import annotations

import json
import logging

from ..chunking.base import Chunk
from .config import Settings
from .db import get_engine, session_scope
from .models import Base, RagChunk

logger = logging.getLogger(__name__)


def apply_schema(settings: Settings) -> None:
    if not settings.database_url:
        return
    engine = get_engine(settings)
    Base.metadata.create_all(bind=engine)
    logger.info("Схема PostgreSQL применена (rag_chunks).")


def persist_chunks_full_refresh(settings: Settings, chunks: list[Chunk]) -> list[str]:
    """
    Полная перезапись чанков для данной коллекции Qdrant, возвращает UUID строк
    в том же порядке, что и chunks (id точек в Qdrant).
    """
    coll = settings.qdrant_collection
    model = settings.embedding_model

    ids: list[str] = []
    with session_scope(settings) as session:
        session.query(RagChunk).filter(RagChunk.qdrant_collection == coll).delete(synchronize_session=False)
        for c in chunks:
            key = c.payload.get("idempotency_key", "")
            if not key:
                raise ValueError("Чанк без idempotency_key, нельзя записать в PostgreSQL")
            st = str(c.payload.get("source_type", ""))
            role = c.payload.get("csv_chunk_role")
            if role is not None:
                role = str(role)
            pay = {k: v for k, v in c.payload.items() if k != "text"}
            row = RagChunk(
                idempotency_key=key,
                source_type=st,
                chunk_role=role,
                searchable_text=c.text,
                payload=json.loads(json.dumps(pay, ensure_ascii=False)),
                embedding_model=model,
                qdrant_collection=coll,
            )
            session.add(row)
            session.flush()
            ids.append(str(row.id))

    logger.info("PostgreSQL: записано %s чанков (коллекция %s).", len(ids), coll)
    return ids
