from __future__ import annotations

import logging

from ..config import Settings
from ..embeddings import embed_texts

logger = logging.getLogger(__name__)


def build_vectors(texts: list[str], settings: Settings) -> list[list[float]]:
    logger.info("Эмбеддинг %s чанков (модель: %s)…", len(texts), settings.embedding_model)
    return embed_texts(texts, settings)

