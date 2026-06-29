"""
bot/utils/file_parser.py
Parse recipient number lists from CSV, Excel, and TXT files
"""

import io
import logging
from typing import List

logger = logging.getLogger(__name__)


async def parse_recipient_file(file_bytes: bytes, filename: str) -> List[str]:
    """
    Parse numbers from uploaded file.

    Supports: .csv, .txt, .xlsx, .xls
    Returns flat list of raw number strings (validation done separately).
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "txt"

    try:
        if ext in ("xlsx", "xls"):
            return _parse_excel(file_bytes, ext)
        elif ext == "csv":
            return _parse_csv(file_bytes)
        else:
            return _parse_txt(file_bytes)
    except Exception:
        logger.exception("Failed to parse file: %s", filename)
        return []


def _parse_txt(file_bytes: bytes) -> List[str]:
    text = file_bytes.decode("utf-8", errors="ignore")
    numbers = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Handle comma-separated on same line
        for part in line.split(","):
            part = part.strip()
            if part:
                numbers.append(part)
    return numbers


def _parse_csv(file_bytes: bytes) -> List[str]:
    import csv
    text = file_bytes.decode("utf-8", errors="ignore")
    numbers = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        for cell in row:
            cell = cell.strip()
            if cell and any(c.isdigit() for c in cell):
                numbers.append(cell)
    return numbers


def _parse_excel(file_bytes: bytes, ext: str) -> List[str]:
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
        numbers = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                for cell in row:
                    if cell is not None:
                        val = str(cell).strip()
                        if val and any(c.isdigit() for c in val):
                            numbers.append(val)
        wb.close()
        return numbers
    except Exception:
        logger.exception("Excel parse failed, trying xlrd")
        try:
            import xlrd
            wb = xlrd.open_workbook(file_contents=file_bytes)
            numbers = []
            for sheet in wb.sheets():
                for row_idx in range(sheet.nrows):
                    for col_idx in range(sheet.ncols):
                        val = str(sheet.cell_value(row_idx, col_idx)).strip()
                        if val and any(c.isdigit() for c in val):
                            numbers.append(val)
            return numbers
        except Exception:
            logger.exception("xlrd parse also failed")
            return []
