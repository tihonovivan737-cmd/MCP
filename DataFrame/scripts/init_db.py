#!/usr/bin/env python3
"""Создание схемы PostgreSQL. Рекомендуемый запуск: `python -m DataFrame init-db`."""

from __future__ import annotations

import sys

from DataFrame.rag.config import load_settings
from DataFrame.rag.logging_utils import configure_logging
from DataFrame.rag.postgres_store import apply_schema


def main() -> None:
    configure_logging()
    s = load_settings()
    if not s.database_url:
        print("Задайте DATABASE_URL, например:", file=sys.stderr)
        print("  export DATABASE_URL='postgresql://user:pass@localhost:5432/ragdb'", file=sys.stderr)
        raise SystemExit(1)
    apply_schema(s)
    print("Схема PostgreSQL создана (таблица rag_chunks).")


if __name__ == "__main__":
    main()
