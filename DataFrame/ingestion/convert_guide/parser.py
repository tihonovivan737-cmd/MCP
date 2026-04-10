from __future__ import annotations

import re

import pandas as pd

from .config import SHEET_CONFIGS, UNIFIED_COLS


def _clean(val):
    if val is None:
        return ""
    s = str(val).strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s


def _is_section_header(row_values: list) -> bool:
    non_empty = [v for v in row_values if v is not None and str(v).strip()]
    if len(non_empty) != 1:
        return False
    text = str(non_empty[0]).strip()
    return len(text) < 100 and (text.isupper() or text == text.title())


def parse_sheet(sheet_name: str, wb) -> pd.DataFrame:
    cfg = SHEET_CONFIGS[sheet_name]
    ws = wb[sheet_name]
    header_row = cfg["header_row"]
    col_map = cfg["col_map"]

    headers_raw = []
    for cell in ws[header_row]:
        val = cell.value
        headers_raw.append(str(val).strip() if val is not None else None)

    col_index = {}
    for raw_name, unified_name in col_map.items():
        for idx, h in enumerate(headers_raw):
            if h and h.strip().rstrip() == raw_name.strip():
                col_index[unified_name] = idx
                break

    rows = []
    current_subcategory = ""
    for row in ws.iter_rows(min_row=header_row + 1, max_row=ws.max_row, values_only=True):
        vals = list(row)
        if _is_section_header(vals):
            current_subcategory = _clean(vals[0])
            continue
        has_data = any(v is not None and str(v).strip() for v in vals)
        if not has_data:
            continue

        record = {col: "" for col in UNIFIED_COLS}
        record["Категория"] = sheet_name
        record["Подкатегория"] = current_subcategory
        record["Лист_источник"] = sheet_name
        for unified_name, idx in col_index.items():
            if idx < len(vals):
                record[unified_name] = _clean(vals[idx])
        rows.append(record)
    return pd.DataFrame(rows, columns=UNIFIED_COLS)


def build_dataframe_from_workbook(wb) -> pd.DataFrame:
    frames = []
    for sheet_name in SHEET_CONFIGS:
        if sheet_name in wb.sheetnames:
            df = parse_sheet(sheet_name, wb)
            df["Строка_источник"] = range(1, len(df) + 1)
            frames.append(df)
            print(f"  [{sheet_name}] -> {len(df)} записей")
        else:
            print(f"  [{sheet_name}] - лист не найден, пропускаю")

    result = pd.concat(frames, ignore_index=True)
    result = result[result["Наименование"].str.strip().astype(bool)].reset_index(drop=True)
    return result

