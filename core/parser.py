
"""
parser.py — Robust PDF parser for purchase orders.

Public API:
    extract_header_meta(pdf_path: str) -> dict
    extract_table_rows(pdf_path: str) -> List[List[Any]]  # includes header row

Strategy (in order):
    1) Position-based reconstruction using pdfplumber.extract_words (best coverage)
    2) Table extraction via pdfplumber.extract_tables (when tables are well-formed)
    3) Regex fallback over normalized text (permissive; no hard dependency on PyPDF2)

Dependencies:
    pdfplumber (primary), openpyxl (only for your Excel writer, not used here).
    PyPDF2 is optional (used only if available).
"""
from __future__ import annotations

import re
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)

HEADER = [
    "Qty",
    "Item_SKU",
    "Dev_Code",
    "UPC",
    "HTS_Code",
    "Brand",
    "Description",
    "Rate",
    "Amount",
]


# ==============================
# Public API
# ==============================

def extract_header_meta(pdf_path: str) -> Dict[str, Any]:
    """Extract key metadata from the first/last pages' text."""
    pages = _extract_all_text(pdf_path)
    page_count = len(pages)
    first = pages[0] if pages else ""

    def _pick(patterns: List[str], text: str) -> str | None:
        for p in patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                return m.group(1).strip()
        return None

    po_number = _pick([r"PO\s*#?\s*(\d{4,})", r"Purchase\s+Order\s*#?\s*(\d{4,})"], first)
    vendor_number = _pick([r"Vendor\s*#\s*(\d+)", r"Vendor\s*No\.?\s*(\d+)"], first)
    ship_by_date = _pick([r"SHIP\s*(?:COMPLETE\s*)?BY\s*DATE:?\s*([\d/\-]{6,10})",
                          r"Ship\s*By:?\s*([\d/\-]{6,10})"], first)
    payment_terms = _pick([r"PAYMENT\s*TERMS:?\s*(.+)", r"Terms:?\s*(.+)"], first)

    total = None
    for t in reversed(pages):
        m = re.search(r"Total\s*\$?\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})", t, flags=re.I)
        if m:
            total = m.group(1)
            break

    return {
        "po_number": po_number or "N/A",
        "vendor_number": vendor_number or "N/A",
        "ship_by_date": ship_by_date or "N/A",
        "payment_terms": payment_terms or "N/A",
        "total": total or "N/A",
        "page_count": page_count,
    }


def extract_table_rows(pdf_path: str) -> List[List[Any]]:
    """Return [HEADER] + data rows. Tries positions → tables → regex."""
    # 1) Position-based
    try:
        rows = _extract_via_positions(pdf_path)
        if _is_reasonable(rows):
            logger.info("Position-based extraction: %d rows", len(rows) - 1)
            return rows
    except Exception as e:
        logger.warning("Position-based extraction failed: %s", e)

    # 2) Table extraction
    try:
        rows = _extract_via_tables(pdf_path)
        if _is_reasonable(rows):
            logger.info("Table extraction: %d rows", len(rows) - 1)
            return rows
    except Exception as e:
        logger.warning("Table extraction failed: %s", e)

    # 3) Regex fallback
    try:
        rows = _extract_via_regex(pdf_path)
        if _is_reasonable(rows):
            logger.info("Regex fallback extraction: %d rows", len(rows) - 1)
            return rows
    except Exception as e:
        logger.error("Regex fallback failed: %s", e)

    logger.error("No items extracted from %s", pdf_path)
    return [HEADER]


# ==============================
# Position-based extraction
# ==============================

def _extract_via_positions(pdf_path: str) -> List[List[Any]]:
    import pdfplumber

    out_rows: List[List[Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            if not words:
                continue

            header_y, col_x = _find_header_and_columns(words)
            if header_y is None or not col_x:
                # header not found; skip page
                continue

            # Group words below header into line bands by Y proximity
            line_tol = 5.5  # points
            bands: List[Tuple[float, List[dict]]] = []
            for w in words:
                cy = (w["top"] + w["bottom"]) / 2.0
                if cy <= header_y:
                    continue
                placed = False
                for i, (y, arr) in enumerate(bands):
                    if abs(y - cy) <= line_tol:
                        arr.append(w)
                        bands[i] = (y, arr)
                        placed = True
                        break
                if not placed:
                    bands.append((cy, [w]))

            bands.sort(key=lambda t: t[0])

            pending = None  # last completed row for wrapped description merge
            for _, arr in bands:
                arr.sort(key=lambda d: d["x0"])

                cells = {k: [] for k in col_x.keys()}
                for w in arr:
                    cx = (w["x0"] + w["x1"]) / 2.0
                    col = _which_col(cx, col_x)
                    if col:
                        cells[col].append(w["text"])

                qty_s = " ".join(cells.get("qty", []))
                sku_s = "".join(cells.get("sku", []))
                dev_s = "".join(cells.get("dev", []))
                upc_s = _first_match("".join(cells.get("upc", [])), r"\b\d{8,14}\b")
                hts_s = _first_match("".join(cells.get("hts", [])), r"\b\d{8,12}\b")
                branddesc = _clean_ws(" ".join(cells.get("branddesc", [])))
                rate_s = "".join(cells.get("rate", []))
                amount_s = "".join(cells.get("amount", []))

                has_key = bool(sku_s and upc_s)

                if not has_key and pending is not None and branddesc:
                    # Continuation line → append to previous description
                    pending[6] = _clean_ws((pending[6] or "") + " " + branddesc)
                    continue

                if not has_key:
                    continue

                qty = _to_int(qty_s)
                rate = _to_float(rate_s)
                amount = _to_float(amount_s)
                if amount is None and (qty is not None) and (rate is not None):
                    amount = round(qty * rate, 2)

                brand, desc = "", branddesc
                if branddesc:
                    parts = branddesc.split(" ", 1)
                    brand = parts[0]
                    desc = parts[1] if len(parts) > 1 else ""

                row = [
                    qty if qty is not None else "",
                    sku_s,
                    dev_s,
                    upc_s,
                    hts_s,
                    brand,
                    desc,
                    rate if rate is not None else "",
                    amount if amount is not None else "",
                ]
                out_rows.append(row)
                pending = row

    # Dedupe by SKU|UPC, keep first (usually richer description)
    seen = set()
    deduped = []
    for r in out_rows:
        key = f"{str(r[1]).strip()}|{str(r[3]).strip()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)

    return [HEADER] + deduped


def _find_header_and_columns(words: List[dict]) -> Tuple[float | None, Dict[str, Tuple[float, float]]]:
    # Cluster words by Y to find header band
    tol = 4.0
    bands: List[Tuple[float, List[dict]]] = []
    for w in words:
        cy = (w["top"] + w["bottom"]) / 2.0
        placed = False
        for i, (y, arr) in enumerate(bands):
            if abs(y - cy) <= tol:
                arr.append(w)
                bands[i] = (y, arr)
                placed = True
                break
        if not placed:
            bands.append((cy, [w]))
    bands.sort(key=lambda t: t[0])

    header = None
    for y, ws in bands[:12]:  # look near the top of the page
        text = " ".join(w["text"].lower() for w in ws)
        has_qty = "qty" in text
        has_sku = ("item" in text and "sku" in text) or "item sku" in text or "sku" in text
        has_upc = "upc" in text
        has_price = ("rate" in text) or ("price" in text)
        has_amount = ("amount" in text) or ("total" in text) or ("amt" in text)
        if has_qty and has_sku and has_upc and (has_price or has_amount):
            header = (y, ws)
            break

    if not header:
        return None, {}

    y, ws = header

    def midx(w: dict) -> float:
        return (w["x0"] + w["x1"]) / 2.0

    centers = {}
    for w in ws:
        t = w["text"].lower()
        if "qty" in t:
            centers.setdefault("qty", []).append(midx(w))
        if ("item" in t) or ("sku" in t):
            centers.setdefault("sku", []).append(midx(w))
        if "dev" in t:
            centers.setdefault("dev", []).append(midx(w))
        if "upc" in t:
            centers.setdefault("upc", []).append(midx(w))
        if "hts" in t:
            centers.setdefault("hts", []).append(midx(w))
        if "rate" in t or "price" in t:
            centers.setdefault("rate", []).append(midx(w))
        if "amount" in t or "total" in t or "amt" in t:
            centers.setdefault("amount", []).append(midx(w))

    centers = {k: sum(v) / len(v) for k, v in centers.items()}
    if not centers:
        return None, {}

    ordered = sorted(centers.items(), key=lambda kv: kv[1])

    ranges: Dict[str, Tuple[float, float]] = {}
    for i, (name, cx) in enumerate(ordered):
        left = (ordered[i - 1][1] + cx) / 2.0 if i > 0 else cx - 70
        right = (ordered[i + 1][1] + cx) / 2.0 if i + 1 < len(ordered) else cx + 70
        ranges[name] = (left, right)

    # Brand/Description region between right edge of (hts|upc|dev|sku) and left edge of (rate|amount)
    left_anchor = ranges.get("hts") or ranges.get("upc") or ranges.get("dev") or ranges.get("sku")
    right_anchor = ranges.get("rate") or ranges.get("amount")
    if left_anchor and right_anchor:
        ranges["branddesc"] = (left_anchor[1], right_anchor[0])

    return y, ranges


def _which_col(x: float, col_x: Dict[str, Tuple[float, float]]) -> str | None:
    for name, (l, r) in col_x.items():
        if l <= x <= r:
            return name
    return None


def _first_match(s: str, pat: str) -> str:
    m = re.search(pat, s or "")
    return m.group(0) if m else ""


# ==============================
# Table extraction (secondary)
# ==============================

def _extract_via_tables(pdf_path: str) -> List[List[Any]]:
    import pdfplumber

    settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_tolerance": 3,
        "intersection_tolerance": 3,
        "min_words_vertical": 1,
        "min_words_horizontal": 1,
        "keep_blank_chars": False,
        "text_tolerance": 2,
        "join_tolerance": 2,
    }

    rows: List[List[Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables(settings)
            except Exception:
                tables = []
            for t in tables:
                table_rows = [[_clean_ws(c) for c in row] for row in t if any(_clean_ws(c) for c in row)]
                if not table_rows:
                    continue

                # find header row
                header_idx = None
                for i, r in enumerate(table_rows[:5]):
                    label = " ".join(c.lower() for c in r)
                    if ("qty" in label) and (("sku" in label) or ("item sku" in label)):
                        header_idx = i
                        break
                if header_idx is None:
                    continue

                for r in table_rows[header_idx + 1:]:
                    qty = _to_int(_safe_pick(r, 0))
                    sku = _safe_pick(r, 1)
                    dev = _safe_pick(r, 2)
                    upc = _first_match(_safe_pick(r, 3) + " " + _safe_pick(r, 4), r"\b\d{8,14}\b")
                    hts = _first_match(_safe_pick(r, 4) + " " + _safe_pick(r, 5), r"\b\d{8,12}\b")
                    branddesc = _clean_ws((_safe_pick(r, 5) + " " + _safe_pick(r, 6)).strip())
                    brand, desc = _split_brand_desc(branddesc)
                    rate = _to_float(_safe_pick(r, -2))
                    amount = _to_float(_safe_pick(r, -1))
                    if amount is None and (qty is not None) and (rate is not None):
                        amount = round(qty * rate, 2)

                    rows.append([
                        qty if qty is not None else "",
                        sku, dev, upc, hts, brand, desc,
                        rate if rate is not None else "",
                        amount if amount is not None else "",
                    ])

    return [HEADER] + _dedupe(rows)


def _safe_pick(row: List[str], idx: int) -> str:
    try:
        return _clean_ws(row[idx])
    except Exception:
        return ""


def _split_brand_desc(s: str) -> Tuple[str, str]:
    s = _clean_ws(s)
    if not s:
        return "", ""
    parts = s.split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


# ==============================
# Regex fallback (permissive)
# ==============================

def _extract_via_regex(pdf_path: str) -> List[List[Any]]:
    text = " ".join(_extract_all_text(pdf_path))
    text = re.sub(r"\s+", " ", text)

    # DEV/HTS optional; brand/desc greedy until first price
    pat = re.compile(
        r"(?P<qty>\d{1,4})\s+"
        r"(?P<sku>[A-Z0-9-]{6,})\s+"
        r"(?P<dev>[A-Z0-9]{2,})?\s*"
        r"(?P<upc>\d{8,14})\s+"
        r"(?P<hts>\d{8,12})?\s*"
        r"(?P<branddesc>[A-Za-z][A-Za-z0-9&'\- ].*?)\s+"
        r"\$?(?P<rate>\d{1,3}(?:,\d{3})*\.\d{2})\s+"
        r"\$?(?P<amount>\d{1,3}(?:,\d{3})*\.\d{2})"
    )

    rows: List[List[Any]] = []
    for m in pat.finditer(text):
        d = m.groupdict()
        qty = _to_int(d.get("qty"))
        rate = _to_float(d.get("rate"))
        amount = _to_float(d.get("amount"))
        if amount is None and (qty is not None) and (rate is not None):
            amount = round(qty * rate, 2)

        brand, desc = _split_brand_desc(d.get("branddesc") or "")
        rows.append([
            qty if qty is not None else "",
            _clean_ws(d.get("sku") or ""),
            _clean_ws(d.get("dev") or ""),
            _clean_ws(d.get("upc") or ""),
            _clean_ws(d.get("hts") or ""),
            brand, desc,
            rate if rate is not None else "",
            amount if amount is not None else "",
        ])

    return [HEADER] + _dedupe(rows)


# ==============================
# Text extraction
# ==============================

def _extract_all_text(pdf_path: str) -> List[str]:
    """Prefer pdfplumber; optionally fall back to PyPDF2 if present."""
    pages: List[str] = []
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                pages.append(p.extract_text() or "")
        return pages
    except Exception as e:
        logger.warning("pdfplumber text extraction failed: %s", e)

    # Optional: PyPDF2 if available
    try:
        from PyPDF2 import PdfReader  # type: ignore
        rdr = PdfReader(pdf_path)
        for pg in rdr.pages:
            pages.append(pg.extract_text() or "")
    except Exception:
        pass

    return pages


# ==============================
# Common utilities
# ==============================

def _clean_ws(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def _to_float(s: str | None) -> float | None:
    if not s:
        return None
    try:
        s2 = str(s).replace("$", "").replace(",", "").strip()
        return float(s2)
    except Exception:
        return None

def _to_int(s: str | None) -> int | None:
    if not s:
        return None
    try:
        n = re.sub(r"[^0-9-]", "", str(s))
        return int(n) if n not in ("", "-") else None
    except Exception:
        return None

def _dedupe(rows: List[List[Any]]) -> List[List[Any]]:
    seen = set()
    out = []
    for r in rows:
        key = f"{str(r[1]).strip()}|{str(r[3]).strip()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out

def _is_reasonable(rows: List[List[Any]]) -> bool:
    return isinstance(rows, list) and len(rows) >= 5  # header + >=4 items
