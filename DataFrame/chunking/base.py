from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """Единая единица для эмбеддинга и Qdrant."""

    text: str
    payload: dict[str, Any]
    chunk_id: str | None = None

    def __post_init__(self) -> None:
        if self.chunk_id is None:
            self.chunk_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    self.payload.get("idempotency_key", self.text[:512]),
                )
            )


def window_split(text: str, max_chars: int, overlap: int) -> list[str]:
    """Скользящее окно по символам с перекрытием."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, max_chars - overlap)
    while start < len(text):
        end = min(start + max_chars, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start += step
    return chunks


def split_by_legal_headings(text: str) -> list[str]:
    """Дробление по типичным заголовкам НПА (статья / ст. N, глава, раздел)."""
    pattern = re.compile(
        r"(?=(?:^|\n)\s*(?:"
        r"(?:Статья|СТАТЬЯ)\s+\d+|"  # Статья 15
        r"ст\.\s*\d+|Ст\.\s*\d+|"  # ст. 15, Ст. 15
        r"Глава|ГЛАВА|Раздел|РАЗДЕЛ)\b)",
        re.MULTILINE | re.IGNORECASE,
    )
    parts = pattern.split(text)
    cleaned = [p.strip() for p in parts if p and p.strip()]
    return cleaned if cleaned else ([text.strip()] if text.strip() else [])
