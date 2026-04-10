from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Chunk, split_by_legal_headings, window_split

if TYPE_CHECKING:
    pass


def _split_page_blocks(page_num: int, page_text: str) -> list[tuple[int, str]]:
    blocks = re.split(r"\n{2,}", page_text)
    out: list[tuple[int, str]] = []
    for b in blocks:
        b = b.strip()
        if len(b) < 3:
            continue
        out.append((page_num, b))
    if not out and page_text.strip():
        out.append((page_num, page_text.strip()))
    return out


def _chunks_from_pages(
    pages: list[tuple[int, str]],
    *,
    logical_name: str,
    path_key: str,
    max_chars: int,
    overlap: int,
) -> list[Chunk]:
    labeled: list[tuple[int, str]] = []
    for pnum, ptext in pages:
        labeled.extend(_split_page_blocks(pnum, ptext))

    raw_pieces: list[tuple[int, str]] = []
    for pnum, block in labeled:
        for piece in split_by_legal_headings(block):
            piece = piece.strip()
            if not piece:
                continue
            raw_pieces.append((pnum, piece))

    chunks: list[Chunk] = []
    part_idx = 0
    for pnum, piece in raw_pieces:
        for win in window_split(piece, max_chars=max_chars, overlap=overlap):
            body = f"{path_key}\n{pnum}\n{win}"
            stable = hashlib.sha256(body.encode("utf-8")).hexdigest()[:32]
            payload = {
                "source_type": "pdf",
                "source_path": path_key,
                "doc_stem": Path(logical_name).stem,
                "page": pnum,
                "part_index": part_idx,
                "idempotency_key": f"pdf:{stable}",
            }
            header = f"[{logical_name}, стр. {pnum}]\n"
            chunks.append(Chunk(text=header + win, payload=payload))
            part_idx += 1

    return chunks


def chunks_from_pdf(
    path: Path,
    *,
    max_chars: int = 2800,
    overlap: int = 200,
) -> list[Chunk]:
    import fitz

    doc = fitz.open(path)
    try:
        pages: list[tuple[int, str]] = []
        for i in range(len(doc)):
            t = doc[i].get_text("text") or ""
            pages.append((i + 1, t))
        return _chunks_from_pages(
            pages,
            logical_name=path.name,
            path_key=str(path.resolve()),
            max_chars=max_chars,
            overlap=overlap,
        )
    finally:
        doc.close()


def chunks_from_pdf_bytes(
    data: bytes,
    logical_name: str,
    *,
    max_chars: int = 2800,
    overlap: int = 200,
) -> list[Chunk]:
    import fitz

    doc = fitz.open(stream=data, filetype="pdf")
    try:
        pages: list[tuple[int, str]] = []
        for i in range(len(doc)):
            t = doc[i].get_text("text") or ""
            pages.append((i + 1, t))
        path_key = f"postgres:{logical_name}"
        return _chunks_from_pages(
            pages,
            logical_name=logical_name,
            path_key=path_key,
            max_chars=max_chars,
            overlap=overlap,
        )
    finally:
        doc.close()
