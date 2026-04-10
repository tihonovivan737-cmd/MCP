from __future__ import annotations

from ..config import Settings
from ..qdrant_store import ensure_collection, get_client, upsert_chunks


def upsert_to_qdrant(
    settings: Settings,
    ids: list[str],
    vectors: list[list[float]],
    payloads: list[dict],
) -> None:
    client = get_client(settings)
    ensure_collection(client, settings)
    upsert_chunks(client, settings, ids, vectors, payloads)

