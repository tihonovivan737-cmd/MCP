"""Конвертация «Путеводителя» в unified knowledge_base.*."""

from __future__ import annotations

from .config import OUT_DIR, SRC
from .io_ops import build_from_disk, build_from_postgres, postgres_files_enabled, save_to_files, save_to_postgres
from .parser import build_dataframe_from_workbook


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Конвертация «Путеводителя» -> Library...\n")

    settings = None
    if postgres_files_enabled():
        settings, df = build_from_postgres(build_dataframe_from_workbook)
        print(f"Источник Excel: PostgreSQL -> {settings.guide_xlsx_document}\n")
    else:
        if not SRC.exists():
            raise SystemExit(f"Нет файла {SRC}")
        df = build_from_disk(SRC, build_dataframe_from_workbook)
        print("Источник Excel: файл на диске\n")

    print(f"\nИтого: {len(df)} мер поддержки\n")
    print(df.info())
    print("\nПервые записи:\n")
    print(df[["Категория", "Подкатегория", "Получатель", "Наименование"]].head(10).to_string())

    csv_path, xlsx_path = save_to_files(df, OUT_DIR)
    print(f"\nСохранено:\n  {csv_path}\n  {xlsx_path}")

    if postgres_files_enabled() and settings is not None:
        save_to_postgres(df, settings)
        print(f"\nЗаписано в PostgreSQL: {settings.knowledge_csv_document}, knowledge_base.xlsx")

    return df


if __name__ == "__main__":
    main()
