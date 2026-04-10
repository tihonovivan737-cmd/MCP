from __future__ import annotations

import io
import os
from pathlib import Path

import pandas as pd


def postgres_files_enabled() -> bool:
    return os.environ.get("SOURCE_FILES_IN_POSTGRES", "").strip().lower() in ("1", "true", "yes", "on")


def build_from_disk(src: Path, build_dataframe_from_workbook_fn):
    import openpyxl

    wb = openpyxl.load_workbook(src, data_only=True)
    return build_dataframe_from_workbook_fn(wb)


def build_from_postgres(build_dataframe_from_workbook_fn):
    import openpyxl

    from ...rag.config import load_settings
    from ...rag.document_store import get_document

    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("SOURCE_FILES_IN_POSTGRES=1 требует DATABASE_URL")
    raw = get_document(settings, settings.guide_xlsx_document)
    if not raw:
        raise SystemExit(
            f"В PostgreSQL нет «{settings.guide_xlsx_document}». "
            f"Загрузите: python3 -m DataFrame upload-source путь/к/{settings.guide_xlsx_document}",
        )
    wb = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    df = build_dataframe_from_workbook_fn(wb)
    return settings, df


def save_to_files(df: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    csv_path = out_dir / "knowledge_base.csv"
    xlsx_path = out_dir / "knowledge_base.xlsx"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    return csv_path, xlsx_path


def save_to_postgres(df: pd.DataFrame, settings) -> None:
    from ...rag.document_store import put_document

    csv_buf = io.StringIO()
    df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
    put_document(settings, settings.knowledge_csv_document, csv_buf.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8")

    xlsx_buf = io.BytesIO()
    df.to_excel(xlsx_buf, index=False, engine="openpyxl")
    put_document(
        settings,
        "knowledge_base.xlsx",
        xlsx_buf.getvalue(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

