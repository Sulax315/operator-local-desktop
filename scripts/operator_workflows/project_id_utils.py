"""
Numeric job / project IDs for workspace indexing (not financial math).

4-digit tokens (e.g. years in filenames) are not treated as project IDs.
"""
from __future__ import annotations

import re

# Job-style codes (e.g. 219128); excludes 4-digit calendar years in paths/filenames.
MIN_PROJECT_ID_LEN = 5
MAX_PROJECT_ID_LEN = 12


def is_valid_operator_project_id(token: str) -> bool:
    t = (token or "").strip()
    if not t.isdigit():
        return False
    n = len(t)
    return MIN_PROJECT_ID_LEN <= n <= MAX_PROJECT_ID_LEN


def extract_project_id_from_rel_and_name(rel_path: str, file_name: str) -> str:
    """
    Prefer a path segment under `financial_reports/<id>/`, then any /digits/ segment, then filename tokens.
    """
    rel = (rel_path or "").replace("\\", "/").strip()
    fn = (file_name or "").strip()
    hay = f"/{rel}/"

    m = re.search(r"/financial_reports/(\d{5,})/", hay, re.IGNORECASE)
    if m and is_valid_operator_project_id(m.group(1)):
        return m.group(1)

    for seg in re.finditer(r"/(\d{5,})/", hay):
        tid = seg.group(1)
        if is_valid_operator_project_id(tid):
            return tid

    merged = f"{rel} {fn}"
    for m2 in re.finditer(r"\b(\d{5,})\b", merged):
        tid = m2.group(1)
        if is_valid_operator_project_id(tid):
            return tid
    return ""
