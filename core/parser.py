"""
parser.py

This module extracts PO header metadata and line items from vendor PDFs using a
tiered strategy:

1) Position-based extraction (preferred): buckets words by column geometry.
2) Table extraction (secondary): uses pdfplumber's table detection.
3) Regex fallback (last resort): permissive text pattern matching.

Public API:
    extract_header_meta(pdf_path: str) -> dict
    extract_table_rows(pdf_path: str) -> list[list[Any]]

Dependencies:
    pdfplumber (primary). PyPDF2 is optional (text fallback only).
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
    """
    Extract high-level PO metadata from the PDF.

    Parses the first page (and scans the last pages for totals) to recover
    fields commonly printed in vendor POs.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A dictionary with keys:
            - "po_number": Purchase order number (str or "N/A").
            - "vendor_number": Vendor identifier (str or "N/A").
            - "ship_by_date": Ship-by date as printed (str or "N/A").
            - "payment_terms": Payment terms (str or "N/A").
            - "total": Document total amount (str or "N/A").
            - "page_count": Number of pages (int).
    """

    pages = _extract_all_text(pdf_path)
    page_count = len(pages)
    first = pages[0] if pages else ""

    def _pick(patterns: List[str], text: str) -> str | None:
        for p in patterns:
            m = re.search(p, text, flags=re.I)
            if m:
                return m.group(1).strip()
        return None

    po_number = _pick(
        [r"PO\s*#?\s*(\d{4,})", r"Purchase\s+Order\s*#?\s*(\d{4,})"], first
    )
    vendor_number = _pick([r"Vendor\s*#\s*(\d+)", r"Vendor\s*No\.?\s*(\d+)"], first)
    ship_by_date = _pick(
        [
            r"SHIP\s*(?:COMPLETE\s*)?BY\s*DATE:?\s*([\d/\-]{6,10})",
            r"Ship\s*By:?\s*([\d/\-]{6,10})",
        ],
        first,
    )
    payment_terms = _pick([r"PAYMENT\s*TERMS:?\s*(.+)", r"Terms:?\s*(.+)"], first)

    total = None
    for t in reversed(pages):
        m = re.search(
            r"Total\s*\$?\s*([0-9]{1,3}(?:,[0-9]{3})*\.[0-9]{2})", t, flags=re.I
        )
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
    """
    Extract line items as a list of rows, prefixed by HEADER.

    Tries position-based extraction first, then table extraction, and finally
    a permissive regex fallback. Each successful extractor must satisfy a basic
    sanity check on the number of rows.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of rows where the first row is HEADER and subsequent rows contain:
        [Qty, Item_SKU, Dev_Code, UPC, HTS_Code, Brand, Description, Rate, Amount].
    """

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
    """
    Position-based extractor using word geometry.

    Groups words into horizontal bands (lines), assigns tokens to columns by
    comparing word midpoints to header-derived x-ranges, and repairs common
    mis-bucketings (e.g., non-numeric HTS -> Brand/Description; stray text under
    price columns). Performs per-line recovery for missing prices and text.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        HEADER + parsed rows as lists in the canonical column order.

    Raises:
        Exception: Propagates unexpected pdfplumber errors to the caller
        (handled by the outer try/except in extract_table_rows).
    """

    import pdfplumber

    out_rows: List[List[Any]] = []
    _HTS_NUM_RE = re.compile(r"^\d{6,12}$")
    money_pat = r"(?:USD\s*)?\$?\d{1,3}(?:,\d{3})*\.\d{2}"
    _MONEY_RE = re.compile(money_pat)

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            if not words:
                continue

            header_y, col_x = _find_header_and_columns(words)
            if header_y is None or not col_x:
                continue

            # Group words into line bands below header
            line_tol = 5.5
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

            pending = None
            for _, arr in bands:
                arr.sort(key=lambda d: d["x0"])
                cells = {k: [] for k in col_x.keys()}
                for w in arr:
                    cx = (w["x0"] + w["x1"]) / 2.0
                    col = _which_col(cx, col_x)
                    tok = w["text"]

                if col == "hts" and not _HTS_NUM_RE.fullmatch(tok):
                    col = "branddesc"
                elif col in ("rate", "amount") and not _MONEY_RE.fullmatch(tok):
                    col = "branddesc"

                if col:
                    cells[col].append(tok)

                qty_s = " ".join(cells.get("qty", []))
                sku_s = "".join(cells.get("sku", []))
                dev_s = "".join(cells.get("dev", []))
                upc_s = _first_match("".join(cells.get("upc", [])), r"\b\d{8,14}\b")
                hts_s = _first_match("".join(cells.get("hts", [])), r"\b\d{8,12}\b")
                branddesc = _clean_ws(" ".join(cells.get("branddesc", [])))

                if not hts_s:
                    spill = [t for t in cells.get("hts", []) if not _HTS_NUM_RE.fullmatch(t)]
                    if spill:
                        branddesc = _clean_ws((branddesc + " " + " ".join(spill)).strip())
                rate_s = "".join(cells.get("rate", []))
                amount_s = "".join(cells.get("amount", []))

                has_key = bool(sku_s and upc_s)

                # Raw line text for fallback recovery
                raw_line = " ".join(w["text"] for w in arr)

                # ---- Fallback 1: recover prices from the raw line if empty ----
                prices = re.findall(money_pat, raw_line)
                rate = _to_float(rate_s) if rate_s else None
                amount = _to_float(amount_s) if amount_s else None
                if (rate is None or amount is None) and prices:
                    if len(prices) >= 2:
                        if rate is None:
                            rate = _to_float(prices[-2])
                        if amount is None:
                            amount = _to_float(prices[-1])
                    elif len(prices) == 1 and amount is None:
                        amount = _to_float(prices[-1])

                # ---- Fallback 2: brand/desc between UPC and first price on the raw line ----
                if not branddesc and upc_s and prices:
                    m_upc = re.search(r"\b" + re.escape(upc_s) + r"\b", raw_line)
                    m_price = re.search(money_pat, raw_line)
                    if m_upc and m_price and m_price.start() > m_upc.end():
                        seg = raw_line[m_upc.end() : m_price.start()]
                        seg = re.sub(r"\s{2,}", " ", seg).strip()
                        if seg:
                            branddesc = seg

                if not has_key and pending is not None and branddesc:
                    pending[6] = _clean_ws((pending[6] or "") + " " + branddesc)
                    continue

                if not has_key:
                    continue

                qty = _to_int(qty_s)
                if amount is None and (qty is not None) and (rate is not None):
                    amount = round(qty * rate, 2)

                # Split brand/desc
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

    return [HEADER] + _dedupe(out_rows)


def _find_header_and_columns(
    words: List[dict],
) -> Tuple[float | None, Dict[str, Tuple[float, float]]]:
    """
    Locate the header band and compute x-ranges for each column.

    Identifies a plausible header line from the top of the page and computes
    column ranges by midpoint ordering. The Brand/Description window is defined
    from the right edge of UPC/HTS/Dev/SKU through the left edge of
    Rate/Unit Price/Amount.

    Args:
        words: pdfplumber word dictionaries for a page.

    Returns:
        A tuple of:
          - header_y: The vertical centerline of the header row (or None).
          - col_x: Mapping of column name -> (left_x, right_x) interval.
    """

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
    for y, ws in bands[:14]:
        text = " ".join(w["text"].lower() for w in ws)
        has_qty = "qty" in text
        has_sku = (
            ("item" in text and "sku" in text) or "item sku" in text or "sku" in text
        )
        has_upc = "upc" in text
        has_price = ("rate" in text) or ("price" in text) or ("unit price" in text)
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
        if "rate" in t or "price" in t or "unit price" in t:
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

    # Brand/Desc region: start at UPC (then HTS/dev/sku) and end at Rate/Amount
    left_anchor = (ranges.get("upc") or ranges.get("hts") or ranges.get("dev") or ranges.get("sku"))
    right_anchor = ranges.get("rate") or ranges.get("amount")
    if left_anchor and right_anchor:
        left_edge = left_anchor[1]
        if "hts" in ranges:
            left_edge = max(left_edge, ranges["hts"][1])
        ranges["branddesc"] = (left_edge, right_anchor[0])

    return y, ranges


def _which_col(x: float, col_x: Dict[str, Tuple[float, float]]) -> str | None:
    """
    Return the column name whose x-range contains the given x-coordinate.

    Args:
        x: Word midpoint x-coordinate.
        col_x: Mapping of column name -> (left_x, right_x).

    Returns:
        The column key if x lies within a range; otherwise None.
    """

    for name, (left, right) in col_x.items():
        if left <= x <= right:
            return name
    return None


def _first_match(s: str, pat: str) -> str:
    """
    Return the first regex match for ``pat`` in ``s``, or an empty string.

    Args:
        s: Input string to search.
        pat: Regex pattern string.

    Returns:
        The first matching substring, or "" if not found.
    """

    m = re.search(pat, s or "")
    return m.group(0) if m else ""


# ==============================
# Table extraction
# ==============================


def _extract_via_tables(pdf_path: str) -> List[List[Any]]:
    """
    Secondary extractor using pdfplumber's table detection.

    Applies line-based table heuristics to locate a header and subsequent rows.
    Performs light normalization and value coercion, and reuses the same row
    schema as the position-based extractor.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        HEADER + parsed rows, or HEADER only if no plausible table is found.
    """
    
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
                table_rows = [
                    [_clean_ws(c) for c in row]
                    for row in t
                    if any(_clean_ws(c) for c in row)
                ]
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

                for r in table_rows[header_idx + 1 :]:
                    qty = _to_int(_safe_pick(r, 0))
                    sku = _safe_pick(r, 1)
                    dev = _safe_pick(r, 2)
                    upc = _first_match(
                        _safe_pick(r, 3) + " " + _safe_pick(r, 4), r"\b\d{8,14}\b"
                    )
                    hts = _first_match(
                        _safe_pick(r, 4) + " " + _safe_pick(r, 5), r"\b\d{8,12}\b"
                    )
                    branddesc = _clean_ws(
                        (_safe_pick(r, 5) + " " + _safe_pick(r, 6)).strip()
                    )
                    brand, desc = _split_brand_desc(branddesc)
                    rate = _to_float(_safe_pick(r, -2))
                    amount = _to_float(_safe_pick(r, -1))
                    if amount is None and (qty is not None) and (rate is not None):
                        amount = round(qty * rate, 2)

                    rows.append(
                        [
                            qty if qty is not None else "",
                            sku,
                            dev,
                            upc,
                            hts,
                            brand,
                            desc,
                            rate if rate is not None else "",
                            amount if amount is not None else "",
                        ]
                    )

    return [HEADER] + _dedupe(rows)


# ==============================
# Regex fallback
# ==============================


def _extract_via_regex(pdf_path: str) -> List[List[Any]]:
    """
    Permissive regex fallback over concatenated page text.

    Useful when geometry/table methods fail. Attempts to parse minimally viable
    item lines containing qty, sku, upc, brand/desc, and price fields.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        HEADER + parsed rows with HTS_Code typically blank (row-level HTS is
        often not printed and cannot be recovered reliably by regex alone).
    """

    text = " ".join(_extract_all_text(pdf_path))
    text = re.sub(r"\s+", " ", text)
    money_pat = r"(?:USD\s*)?\$?\d{1,3}(?:,\d{3})*\.\d{2}"
    _MONEY_RE = re.compile(money_pat)

    pat = re.compile(
        r"(?P<qty>\d{1,4})\s+"
        r"(?P<sku>[A-Z0-9]{1}[A-Z]{2}\d{4}-\d{2}-[A-Z]\d{4}-[A-Z0-9]{5})\s+"
        r"(?P<dev>[A-Z0-9]{2,})?\s*"
        r"(?P<upc>\d{8,14})\s+"
        r"(?P<branddesc>.+?)\s+"
        r"(?P<rate>" + money_pat + r")\s+"
        r"(?P<amount>" + money_pat + r")"
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
        rows.append(
            [
                qty if qty is not None else "",
                _clean_ws(d.get("sku") or ""),
                _clean_ws(d.get("dev") or ""),
                _clean_ws(d.get("upc") or ""),
                "",
                brand,
                desc,
                rate if rate is not None else "",
                amount if amount is not None else "",
            ]
        )

    return [HEADER] + _dedupe(rows)


# ==============================
# Text & utilities
# ==============================


def _extract_all_text(pdf_path: str) -> List[str]:
    """
    Extract page texts from the PDF.

    Prefers pdfplumber; if it fails, falls back to PyPDF2 when available.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        A list of raw page strings (one per page). Missing/failed pages return "".
    """

    pages: List[str] = []
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            for p in pdf.pages:
                pages.append(p.extract_text() or "")
        return pages
    except Exception as e:
        logger.warning("pdfplumber text extraction failed: %s", e)
    try:
        from PyPDF2 import PdfReader  # optional

        rdr = PdfReader(pdf_path)
        for pg in rdr.pages:
            pages.append(pg.extract_text() or "")
    except Exception:
        pass
    return pages


def _clean_ws(s: str | None) -> str:
    """
    Normalize whitespace: strip ends and collapse internal runs to single spaces.

    Args:
        s: Input string or None.

    Returns:
        Cleaned string ("" if input is None).
    """
    
    return re.sub(r"\s+", " ", (s or "").strip())


def _to_float(s: str | None) -> float | None:
    """
    Parse a currency-like string to float.

    Removes "$", commas, and optional leading "USD". Returns None on failure.

    Args:
        s: String containing a monetary value.

    Returns:
        Parsed float value, or None if parsing fails.
    """

    if not s:
        return None
    try:
        s2 = str(s).replace("$", "").replace(",", "").strip()
        if s2.upper().startswith("USD"):
            s2 = s2[3:].strip()
        return float(s2)
    except Exception:
        return None


def _to_int(s: str | None) -> int | None:
    """
    Parse an integer from a string, keeping only digits and a leading minus.

    Args:
        s: String containing an integer-like token.

    Returns:
        Parsed integer, or None if parsing fails or the token is empty.
    """

    if not s:
        return None
    try:
        n = re.sub(r"[^0-9-]", "", str(s))
        return int(n) if n not in ("", "-") else None
    except Exception:
        return None


def _dedupe(rows: List[List[Any]]) -> List[List[Any]]:
    """
    Remove duplicate item rows by (SKU, UPC) key.

    Args:
        rows: Parsed item rows (without HEADER).

    Returns:
        A new list of rows with duplicates removed, preserving order.
    """

    seen = set()
    out = []
    for r in rows:
        key = f"{str(r[1]).strip()}|{str(r[3]).strip()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _safe_pick(row: List[str], idx: int) -> str:
    """
    Safely pick and clean a cell from a row by index.

    Args:
        row: Row list.
        idx: Index to fetch.

    Returns:
        Cleaned cell text, or "" if out-of-range or on error.
    """

    try:
        return _clean_ws(row[idx])
    except Exception:
        return ""


def _split_brand_desc(s: str) -> Tuple[str, str]:
    """
    Split a combined Brand/Description string at the first space.

    Args:
        s: Input string containing brand and description.

    Returns:
        A (brand, description) tuple. If no space is present, description is "".
    """

    s = _clean_ws(s)
    if not s:
        return "", ""
    parts = s.split(" ", 1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def _is_reasonable(rows: List[List[Any]]) -> bool:
    """
    Light sanity check for extracted rows.

    Args:
        rows: Candidate output from an extractor.

    Returns:
        True if the structure is a list with a minimum expected number of rows;
        otherwise False.
    """

    return isinstance(rows, list) and len(rows) >= 5
