from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .config import Settings
from .embeddings import embedding_dim

logger = logging.getLogger(__name__)


def get_client(settings: Settings) -> QdrantClient:
    if settings.qdrant_url:
        return QdrantClient(url=settings.qdrant_url)
    path = settings.qdrant_local_path
    if path is None:
        raise ValueError("qdrant_local_path не задан")
    path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(path))


def ensure_collection(client: QdrantClient, settings: Settings) -> None:
    name = settings.qdrant_collection
    dim = embedding_dim(settings)
    exists = False
    try:
        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection_name=name)
        else:
            cols = client.get_collections().collections
            exists = any(c.name == name for c in cols)
    except Exception:
        exists = False

    if exists:
        try:
            info = client.get_collection(collection_name=name)
            vec_cfg = info.config.params.vectors
            existing = getattr(vec_cfg, "size", None)
            if existing is not None and int(existing) != int(dim):
                logger.warning(
                    "Коллекция «%s»: размерность %s ≠ модели (%s). Пересоздаю коллекцию.",
                    name,
                    existing,
                    dim,
                )
                client.delete_collection(collection_name=name)
                exists = False
        except Exception as exc:
            logger.warning("Не удалось проверить коллекцию «%s»: %s", name, exc)

    if not exists:
        client.create_collection(
            collection_name=name,
            vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
        )


def upsert_chunks(
    client: QdrantClient,
    settings: Settings,
    ids: list[str],
    vectors: list[list[float]],
    payloads: list[dict[str, Any]],
    batch_size: int = 64,
) -> None:
    for start in range(0, len(ids), batch_size):
        batch_ids = ids[start : start + batch_size]
        batch_vec = vectors[start : start + batch_size]
        batch_pay = payloads[start : start + batch_size]
        points = [
            qm.PointStruct(id=pid, vector=vec, payload=pay)
            for pid, vec, pay in zip(batch_ids, batch_vec, batch_pay, strict=True)
        ]
        client.upsert(
            collection_name=settings.qdrant_collection,
            points=points,
            wait=True,
        )


def search(
    client: QdrantClient,
    settings: Settings,
    query_vector: list[float],
    limit: int,
    query_filter: qm.Filter | None = None,
) -> list[qm.ScoredPoint]:
    res = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )
    return list(res.points)
