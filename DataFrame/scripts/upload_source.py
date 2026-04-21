#!/usr/bin/env python3
"""
Загрузка PDF / XLSX / CSV в PostgreSQL (таблица source_documents).

После загрузки по умолчанию пересобирается индекс (чанки → Qdrant, при DATABASE_URL — rag_chunks).
Для файла с именем GUIDE_XLSX_DOCUMENT сначала выполняется convert_guide (Excel → CSV в БД).

Примеры:
  python3 scripts/upload_source.py Library/ТКРФ.pdf
  python3 scripts/upload_source.py --name Путеводитель.xlsx ~/Downloads/guide.xlsx
  python3 scripts/upload_source.py --no-index Library/НКРФ.pdf
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from DataFrame.rag.config import load_settings
from DataFrame.rag.document_store import put_file_path
from DataFrame.rag.ingest_pipeline import ingest
from DataFrame.rag.logging_utils import configure_logging
from DataFrame.rag.postgres_store import apply_schema


def _run_convert_guide_trusting_postgres() -> None:
    """convert_guide читает Excel из PG только при SOURCE_FILES_IN_POSTGRES; на время вызова включаем."""
    old = os.environ.get("SOURCE_FILES_IN_POSTGRES")
    os.environ["SOURCE_FILES_IN_POSTGRES"] = "1"
    try:
        try:
            from DataFrame.ingestion.convert_guide.convert_guide import main as convert_main
        except Exception:
            from ingestion.convert_guide.convert_guide import main as convert_main
        convert_main()
    finally:
        if old is None:
            os.environ.pop("SOURCE_FILES_IN_POSTGRES", None)
        else:
            os.environ["SOURCE_FILES_IN_POSTGRES"] = old


def main(argv: list[str] | None = None) -> None:
    configure_logging()
    p = argparse.ArgumentParser(description="Загрузка файла в PostgreSQL (source_documents)")
    p.add_argument("file", type=Path, help="Путь к файлу на диске")
    p.add_argument(
        "--name",
        type=str,
        default=None,
        help="Логическое имя в БД (по умолчанию — basename файла)",
    )
    p.add_argument("--init-schema", action="store_true", help="Создать таблицы перед загрузкой")
    p.add_argument(
        "--no-index",
        action="store_true",
        help="Не строить индекс после загрузки (только запись в source_documents)",
    )
    args = p.parse_args(argv)

    s = load_settings()
    if not s.database_url:
        print("Задайте DATABASE_URL", file=sys.stderr)
        raise SystemExit(1)

    if args.init_schema:
        apply_schema(s)

    path = args.file.expanduser().resolve()
    if not path.is_file():
        print(f"Не файл: {path}", file=sys.stderr)
        raise SystemExit(1)

    logical = args.name or path.name
    put_file_path(s, path, logical_name=logical)
    print(f"OK: {logical} ← {path}")

    if args.no_index:
        return

    if logical == s.guide_xlsx_document:
        print("\nОбновление путеводителя (Excel → CSV в PostgreSQL и Library)…\n")
        _run_convert_guide_trusting_postgres()

    print("\nИндексация (чанки из PostgreSQL при необходимости)…\n")
    n = ingest(s, use_pg_sources=True)
    extra = f" + PostgreSQL rag_chunks" if s.database_url else ""
    print(f"Готово: {n} чанков → Qdrant «{s.qdrant_collection}»{extra}")


if __name__ == "__main__":
    main()
