from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from ..config import Settings


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def write_manifest(settings: Settings, *, chunks_total: int) -> None:
    sources: dict = {"csv_sha256": None, "pdf_sha256": []}
    if settings.knowledge_csv.exists():
        sources["csv_sha256"] = _file_sha256(settings.knowledge_csv)
    for p in settings.pdf_paths:
        if p.exists():
            sources["pdf_sha256"].append({"path": str(p), "sha256": _file_sha256(p)})

    settings.write_manifest(
        {
            "built_at": datetime.now(timezone.utc).isoformat(),
            "chunks_total": chunks_total,
            "sources": sources,
        }
    )

