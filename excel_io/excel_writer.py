"""
excel_writer.py

Excel writer for two layouts:
  - "standard": flat 'Orders' sheet (existing behavior)
  - "sizesheet": matrix sheet that pivots quantities by size

This version is tailored for PDFs that export rows with headers like:
  Qty | Item SKU | Dev Code | UPC | HTS Code | Brand | Description | Rate | Amount

It automatically:
  - maps those headers to canonical fields,
  - infers the size from Description or Item SKU suffixes,
  - preserves the original PDF row order in the SizeSheet,
  - builds a SizeSheet: [DEV # | ITEM | NS DESCRIPTION | size columns | Total]
"""

from __future__ import annotations

import re
import logging
from typing import Dict, Iterable, Optional, Tuple, List

import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side


# ==============================================================================
# Configuration
# ==============================================================================

# Preferred left-to-right order for size columns in the SizeSheet.
# Unknown sizes found in the data will be appended to the right automatically.
SIZESHEET_SIZE_ORDER: List[str] = [
    "One size",
    "0-3m", "3-6m", "6-12m", "12-18m", "18-24m",
    "2T", "3T", "4T", "5", "6", "7", "8", "9", "10",
]

# Mapping from canonical internal field names -> final SizeSheet headers.
BASE_COLS_MAP: Dict[str, str] = {
    "dev_no": "DEV #",               # mapped from "Dev Code"
    "item": "ITEM",                  # mapped from "Item SKU"
    "ns_description": "NS DESCRIPTION",  # mapped from "Description"
}

# Column alias sets used to map whatever headings come from the PDF to
# canonical internal names. These are *case-insensitive* matches.
COLUMN_ALIASES: Dict[str, Tuple[str, ...]] = {
    "dev_no": ("dev no", "dev #", "dev#", "dev code", "dev_code", "dev", "devcode"),
    "item": ("item", "item sku", "item_sku", "sku"),
    "ns_description": ("ns description", "description", "desc", "item description"),
    "qty": ("qty", "quantity", "order qty", "ordered qty"),
    "size_label": ("size_label", "size", "size name"),
    "rate": ("rate", "price"),
    "amount": ("amount", "line total", "extended price", "ext price"),
    "upc": ("upc", "barcode"),
    "hts_code": ("hts code", "hts", "hs code"),
    "brand": ("brand",),
}

# Regex to pull a trailing size token from Description, tolerating different dashes.
# Matches: "... - 3-6m", "... - 2T", "... - 10", "... One size"
_DESCRIPTION_SIZE_RE = re.compile(
    r"(?:[-–—]\s*|\s)(One size|0-3m|3-6m|6-12m|12-18m|18-24m|2T|3T|4T|5|6|7|8|9|10)\s*$",
    flags=re.IGNORECASE,
)

# SKU suffix → size label map for robust fallback when Description doesn’t contain a size.
# Examples observed in your PDFs (RuffleButts/RuggedButts SKUs):
SKU_SUFFIX_TO_SIZE: Dict[str, str] = {
    "03M00": "0-3m",
    "0306M": "3-6m",
    "0612M": "6-12m",
    "1218M": "12-18m",
    "1824M": "18-24m",
    "2T000": "2T",
    "3T000": "3T",
    "4T000": "4T",
    "5K000": "5",
    "6K000": "6",
    "7K000": "7",
    "8K000": "8",
    "K0000": "10",   # observed pattern where plain K0000 maps to size 10
}


# ==============================================================================
# Public API
# ==============================================================================

def write_to_excel(
    df: pd.DataFrame,
    meta: dict,
    output_path: str,
    *,
    layout: str = "standard",
) -> None:
    """
    Write an Excel workbook with a Summary sheet and either:
      - flat 'Orders' (layout="standard"), or
      - pivoted 'SizeSheet' (layout="sizesheet").

    Parameters
    ----------
    df : pd.DataFrame
        Parsed order rows. For SizeSheet, rows may be flat (one row per size),
        as per the PDF, and we will infer a 'size_label' if missing.
    meta : dict
        PO metadata for the Summary sheet (PO number, vendor, dates, etc.).
    output_path : str
        Filesystem path where the .xlsx file should be saved.
    layout : {"standard", "sizesheet"}, default "standard"
        Which secondary sheet to add next to Summary.
    """
    try:
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            # --- Summary (always present) ---
            _create_summary_sheet(writer, meta)

            if layout.lower() == "sizesheet":
                # Build SizeSheet from PDF-like columns.
                size_df = _to_sizesheet_dataframe(df)
                size_df.to_excel(writer, sheet_name="SizeSheet", index=False)
                _format_sizesheet(writer.sheets["SizeSheet"], size_df)
            else:
                # Keep existing flat 'Orders' layout.
                df.to_excel(writer, sheet_name="Orders", index=False)
                _format_orders_sheet(writer.sheets["Orders"], df)

        logging.info("Excel file written successfully: %s", output_path)
    except Exception as e:
        logging.error("Error writing Excel file: %s", e)
        raise


# ==============================================================================
# Summary sheet
# ==============================================================================

def _create_summary_sheet(writer, meta: dict) -> None:
    """Create a concise Summary sheet with key PO metadata."""
    summary_data = {
        "Field": [
            "PO Number",
            "Vendor Number",
            "Ship By Date",
            "Payment Terms",
            "Total Amount",
            "Page Count",
            "Processing Date",
        ],
        "Value": [
            meta.get("po_number", "N/A"),
            meta.get("vendor_number", "N/A"),
            meta.get("ship_by_date", "N/A"),
            meta.get("payment_terms", "N/A"),
            f"${meta.get('total', 'N/A')}" if meta.get("total") != "N/A" else "N/A",
            str(meta.get("page_count", "N/A")),
            pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        ],
    }
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name="Summary", index=False)
    _format_summary_sheet(writer.sheets["Summary"])


def _format_summary_sheet(ws) -> None:
    """Apply consistent styles and borders to the Summary sheet."""
    # Header
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Body
    data_font = Font(size=11)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = data_font
            cell.alignment = Alignment(horizontal="left", vertical="center")

    # Column widths
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 30

    # Borders
    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin


# ==============================================================================
# Orders (flat) sheet — existing behavior
# ==============================================================================

def _format_orders_sheet(ws, df: pd.DataFrame) -> None:
    """Format the flat 'Orders' sheet with readable headers, autosizing, and borders."""
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    data_font = Font(size=10)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = data_font
            cell.alignment = Alignment(horizontal="left", vertical="center")

    # Autosize with semantic caps
    for col_idx, col in enumerate(df.columns, start=1):
        letter = get_column_letter(col_idx)
        if len(df) > 0:
            max_len = max(len(str(col)), df[col].astype(str).str.len().max())
        else:
            max_len = len(str(col))

        col_lower = str(col).lower()
        if col_lower in {"description"}:
            width = min(max_len + 4, 50)
        elif col_lower in {"qty", "rate", "amount"}:
            width = max(max_len + 2, 12)
        elif col_lower in {"item_sku", "dev_code", "dev no", "dev_no", "item"}:
            width = max(max_len + 2, 15)
        elif col_lower in {"upc", "hts code", "hts_code"}:
            width = max(max_len + 2, 18)
        else:
            width = max_len + 2

        ws.column_dimensions[letter].width = width

    # Currency formatting for rate/amount if present
    currency_fmt = '"$"#,##0.00'
    for col_idx, col in enumerate(df.columns, start=1):
        if str(col).lower() in {"rate", "amount"}:
            letter = get_column_letter(col_idx)
            for row in range(2, len(df) + 2):
                ws[f"{letter}{row}"].number_format = currency_fmt

    thin = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin

    # Zebra striping
    light_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    for r_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if r_idx % 2 == 0:
            for cell in row:
                cell.fill = light_fill


# ==============================================================================
# SizeSheet (matrix) — new layout
# ==============================================================================

def _to_sizesheet_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert a flat PDF-like DataFrame to a matrix suitable for 'SizeSheet'.

    Expected input columns (any case, minor variations ok):
      - Qty
      - Item SKU
      - Dev Code
      - Description
    Optional:
      - size/size_label (if the parser already extracted it)
      - UPC, HTS Code, Brand, Rate, Amount (ignored here)

    Steps:
      1) map incoming column names to canonical fields,
      2) ensure a 'size_label' exists (infer from Description or Item SKU),
      3) **preserve original row order** using a helper column,
      4) pivot sizes into columns, add Total,
      5) rename left columns to match SizeSheet headers.
    """
    if df is None or df.empty:
        cols = [BASE_COLS_MAP["dev_no"], BASE_COLS_MAP["item"], BASE_COLS_MAP["ns_description"]] + SIZESHEET_SIZE_ORDER + ["Total"]
        return pd.DataFrame(columns=cols)

    # ---- 1) Standardize column names to lowercase for matching ----
    col_lookup = {c.lower().strip(): c for c in df.columns}

    def pick(options: Iterable[str]) -> Optional[str]:
        """Return the actual column name from the DataFrame matching any of the options (case-insensitive)."""
        for opt in options:
            if opt in col_lookup:
                return col_lookup[opt]
        return None

    # Map required canonical fields from aliases
    dev_col = pick(COLUMN_ALIASES["dev_no"])
    item_col = pick(COLUMN_ALIASES["item"])
    desc_col = pick(COLUMN_ALIASES["ns_description"])
    qty_col = pick(COLUMN_ALIASES["qty"])
    size_col = pick(COLUMN_ALIASES["size_label"])  # may be None; we will infer

    missing = [name for name, col in {
        "Dev Code": dev_col, "Item SKU": item_col, "Description": desc_col, "Qty": qty_col
    }.items() if col is None]

    if missing:
        raise ValueError(
            f"SizeSheet: required columns not found in input: {', '.join(missing)}. "
            "Make sure your parser preserves PDF headers or extend COLUMN_ALIASES."
        )

    # ---- 2) Ensure 'size_label' exists; infer when absent or blank ----
    work = df.copy()

    # Preserve original row order before any grouping/pivot (critical)
    work["__order__"] = range(len(work))

    # Normalize/compute size_label if needed
    if size_col is None or work[size_col].isna().all():
        work["__size_label__"] = work.apply(
            lambda r: _infer_size_from_row(
                description=str(r.get(desc_col, "")),
                item_sku=str(r.get(item_col, "")),
            ),
            axis=1,
        )
        size_col = "__size_label__"
    else:
        # Clean existing size strings
        work[size_col] = (
            work[size_col]
            .astype(str)
            .str.replace("–", "-", regex=False)
            .str.replace("—", "-", regex=False)
            .str.strip()
        )

    # Coerce qty to numeric (defensive)
    work["__qty__"] = pd.to_numeric(work[qty_col], errors="coerce").fillna(0).astype(int)

    # ---- 3) Pivot: sizes -> columns (sum quantities) while preserving order ----
    pivot = (
        work.pivot_table(
            index=["__order__", dev_col, item_col, desc_col],
            columns=size_col,
            values="__qty__",
            aggfunc="sum",
            fill_value=0,
            observed=False,
        )
        .reset_index()
    )

    # Restore original order and drop the helper
    pivot = pivot.sort_values("__order__").drop(columns="__order__")

    # Determine final ordered size columns: preferred order + any extras found
    present_sizes = [c for c in pivot.columns if c not in (dev_col, item_col, desc_col)]
    extras = [s for s in present_sizes if s not in SIZESHEET_SIZE_ORDER]
    ordered_sizes = SIZESHEET_SIZE_ORDER + [s for s in extras if s not in SIZESHEET_SIZE_ORDER]

    # Reindex to desired order (missing sizes will be added with 0)
    pivot = pivot.set_index([dev_col, item_col, desc_col])
    pivot = pivot.reindex(columns=ordered_sizes, fill_value=0).reset_index()

    # Add row total
    pivot["Total"] = pivot[ordered_sizes].sum(axis=1)

    # ---- 5) Rename ID/descriptor headers for the SizeSheet ----
    pivot = pivot.rename(
        columns={
            dev_col: BASE_COLS_MAP["dev_no"],
            item_col: BASE_COLS_MAP["item"],
            desc_col: BASE_COLS_MAP["ns_description"],
        }
    )

    # Ensure final column order
    final_cols = [BASE_COLS_MAP["dev_no"], BASE_COLS_MAP["item"], BASE_COLS_MAP["ns_description"]] + ordered_sizes + ["Total"]
    pivot = pivot[final_cols]

    return pivot


def _infer_size_from_row(description: str, item_sku: str) -> str:
    """
    Infer a size label from Description or, failing that, from the Item SKU suffix.

    Examples matched in Description:
      "... - 3-6m", "... - 2T", "... - 10", "... - One size"

    Examples matched in SKU suffix:
      "...-0306M" -> "3-6m", "...-2T000" -> "2T", "...-5K000" -> "5", "...-K0000" -> "10"
    """
    desc = (description or "").strip()

    # Try Description first (most human-readable)
    m = _DESCRIPTION_SIZE_RE.search(desc)
    if m:
        return _normalize_size_token(m.group(1))

    # Fall back to SKU suffix decoding
    sku = (item_sku or "").strip().upper()
    # Take the last 5 chars; handles patterns like 0306M / 2T000 / 5K000 / K0000
    suffix = sku[-5:]
    size = SKU_SUFFIX_TO_SIZE.get(suffix)
    if size:
        return size

    # Some SKUs might carry a 6-char terminal token (defensive)
    suffix6 = sku[-6:]
    for key, val in SKU_SUFFIX_TO_SIZE.items():
        if suffix6.endswith(key):
            return val

    # If unknown, return as-is “Unknown” bucket so it still pivots
    return "Unknown"


def _normalize_size_token(token: str) -> str:
    """Canonicalize minor variations in size tokens."""
    t = (token or "").strip().replace("–", "-").replace("—", "-")
    if t.lower() in {"one size", "onesize", "os"}:
        return "One size"
    return t


def _format_sizesheet(ws, df: pd.DataFrame) -> None:
    """
    Apply a compact grid style for the SizeSheet:
      - bold colored header,
      - left-aligned ID/description, centered size quantities,
      - frozen header row,
      - borders and zebra striping,
      - sensible column widths (description wider).
    """
    # Header styling
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # Body alignment: first 3 columns left, rest centered
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.column <= 3:
                cell.alignment = Alignment(horizontal="left", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.font = Font(size=10)

    # Autosize columns
    for col_idx, col in enumerate(df.columns, start=1):
        letter = get_column_letter(col_idx)
        if len(df) > 0:
            max_len = max(len(str(col)), df[col].astype(str).head(500).str.len().max())
        else:
            max_len = len(str(col))

        if col in ("NS DESCRIPTION",):
            width = min(max_len + 4, 60)
        elif col in ("DEV #", "ITEM"):
            width = max(max_len + 2, 14)
        else:
            width = max(6, min(max_len + 1, 10))  # keep size columns compact
        ws.column_dimensions[letter].width = width

    # Freeze header
    ws.freeze_panes = "A2"

    # Borders
    thin = Border(left=Side(style="thin"), right=Side(style="thin"),
                  top=Side(style="thin"), bottom=Side(style="thin"))
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin

    # Zebra striping
    light = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    for r_idx, row in enumerate(ws.iter_rows(min_row=2), start=2):
        if r_idx % 2 == 0:
            for cell in row:
                cell.fill = light
