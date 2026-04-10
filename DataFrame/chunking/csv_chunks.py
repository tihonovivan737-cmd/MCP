from __future__ import annotations

import io
import json
from pathlib import Path

import pandas as pd

from .base import Chunk
from .schema import CSV_CHUNK_GROUPS


def _cell(row: dict, key: str) -> str:
    v = row.get(key)
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _group_to_lines(row: dict, keys: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for key in keys:
        val = _cell(row, key)
        if val:
            lines.append(f"{key}: {val}")
    return lines


def _anchor_header(row: dict) -> str:
    cat = _cell(row, "Категория")
    sub = _cell(row, "Подкатегория")
    name = _cell(row, "Наименование")
    parts = ["Мера поддержки (справочник)"]
    if cat:
        parts.append(cat)
    if sub:
        parts.append(sub)
    head = " | ".join(parts)
    if name:
        return f"[{head}]\nНаименование: {name}\n\n"
    return f"[{head}]\n\n"


def chunks_from_dataframe(df: pd.DataFrame, source_label: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    path_key = source_label

    for row_index, (_, row) in enumerate(df.iterrows()):
        r = row.to_dict()
        anchor = _anchor_header(r)
        row_json = json.dumps(
            {k: ("" if pd.isna(v) else str(v)) for k, v in r.items()},
            ensure_ascii=False,
        )

        base_payload = {
            "source_type": "csv",
            "source_path": path_key,
            "row_index": row_index,
            "Категория": _cell(r, "Категория"),
            "Подкатегория": _cell(r, "Подкатегория"),
            "Наименование": _cell(r, "Наименование"),
            "Лист_источник": _cell(r, "Лист_источник"),
            "Строка_источник": _cell(r, "Строка_источник"),
            "row_json": row_json,
        }

        for role, keys in CSV_CHUNK_GROUPS:
            lines = _group_to_lines(r, keys)
            if not lines:
                continue
            body = "\n".join(lines)
            text = f"{anchor}Часть: {role}\n{body}"
            payload = {
                **base_payload,
                "csv_chunk_role": role,
                "idempotency_key": f"csv:{path_key}:{row_index}:{role}",
            }
            chunks.append(Chunk(text=text, payload=payload))

    return chunks


def chunks_from_csv(csv_path: Path) -> list[Chunk]:
    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    return chunks_from_dataframe(df, str(csv_path.resolve()))


def chunks_from_csv_bytes(data: bytes, source_label: str) -> list[Chunk]:
    df = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")
    return chunks_from_dataframe(df, source_label)
