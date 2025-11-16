import pandas as pd
import re

REQUIRED_COLS = ["Qty","Item_SKU","Dev_Code","UPC","HTS_Code","Brand","Description","Rate","Amount"]

def _to_money(s):
    """
    Parse money strings like 'USD 1,234.56' or '($7.89)' to float; returns NaN on failure.
    """
    import math
    if s is None:
        return math.nan
    txt = str(s).strip()
    neg = False
    if txt.startswith("USD"):
        txt = txt[3:].strip()
    if txt.startswith("(") and txt.endswith(")"):
        neg = True
        txt = txt[1:-1].strip()
    txt = txt.replace("$", "").replace(",", "")
    try:
        val = float(txt)
        return -val if neg else val
    except ValueError:
        return math.na

def _upc_ok(upc):
    m = re.fullmatch(r"\d{12}", str(upc))
    if not m:
        return False
    ds = list(map(int, str(upc)))
    check = (10 - ((sum(ds[0:11:2])*3 + sum(ds[1:11:2])) % 10)) % 10
    return check == ds[-1]

def run_qa_checks(df: pd.DataFrame, meta: dict) -> dict:
    """
    Run QA validations on the parsed DataFrame and optional metadata.

    Checks include:
        1) Required columns present.
        2) Quantity values are positive.
        3) UPC format and check digit validation (UPC-A).
        4) Arithmetic integrity: |Qty*Rate - Amount| <= 0.01 for rows with prices.
        5) Optional reconciliation of workbook total against PDF header total.

    Args:
        df: DataFrame of extracted order rows.
        meta: Metadata dictionary that may include a 'total' string value.

    Returns:
        A dictionary with:
            - ok: Boolean indicating whether all checks passed.
            - summary: List of human-readable issue descriptions.
    """
    issues = []

    # 1) Columns present
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        issues.append(f"Missing columns: {', '.join(missing)}")

    if not df.empty:
        # Skip Value-level checks unless the needed columns exist.
        needed = {"Qty", "UPC", "Rate", "Amount"}
        if not needed.issubset(df.columns):
            return {"ok": False, "summary": issues}
 
        # 2) Types and basic ranges
        bad_qty = df.loc[pd.to_numeric(df.get("Qty"), errors="coerce").fillna(-1) <= 0]
        if not bad_qty.empty:
            issues.append(f"{len(bad_qty)} rows have non-positive Qty")

        # 3) UPC format + check digit
        upc_series = df.get("UPC").astype(str).str.replace(r"\D","", regex=True)
        bad_upc = df.loc[~upc_series.map(_upc_ok)]
        if not bad_upc.empty:
            issues.append(f"{len(bad_upc)} rows fail UPC-A check digit")

        # 4) Arithmetic integrity: |Qty*Rate - Amount| <= 0.01
        q = pd.to_numeric(df.get("Qty"), errors="coerce").fillna(0)
        r = pd.to_numeric(df.get("Rate").astype(str).str.replace(r"[^0-9\.\-]", "", regex=True), errors="coerce")
        a = pd.to_numeric(df.get("Amount").astype(str).str.replace(r"[^0-9\.\-]", "", regex=True), errors="coerce")
        missing_prices = r.isna() | a.isna()
        bad_amt = ((q*r - a).abs() > 0.01) & ~missing_prices
        n_bad = int(bad_amt.sum())
        if n_bad:
            issues.append(f"{n_bad} rows where Qty*Rate != Amount")
        if int (missing_prices.sum()):
            issues.append(f"{int(missing_prices.sum())} rows with missing Rate or Amount")
        # 5) PO grand total reconciliation (if present in meta)
        if str(meta.get("total","")).strip() not in ("","N/A", "None"):
            target = _to_money(meta["total"])
            valid_amt = a.dropna()
            actual = float(valid_amt.sum()) if not valid_amt.empty else float("nan")
            if pd.notna(actual) and abs(actual - target) > 0.01:
                issues.append(f"Grand total mismatch: parsed=${actual:,.2f}, PDF=${target:,.2f}")

    return {"ok": len(issues) == 0, "summary": issues}
