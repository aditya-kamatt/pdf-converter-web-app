import pandas as pd
import re

REQUIRED_COLS = ["Qty","Item_SKU","Dev_Code","UPC","Brand","Description","Rate","Amount"]

def _to_money(s):
    return float(str(s).replace("$","").replace(",","").strip())

def _upc_ok(upc):
    m = re.fullmatch(r"\d{12}", str(upc))
    if not m: return False
    ds = list(map(int, str(upc)))
    check = (10 - ((sum(ds[0:11:2])*3 + sum(ds[1:11:2])) % 10)) % 10
    return check == ds[-1]

def run_qa_checks(df: pd.DataFrame, meta: dict) -> dict:
    issues = []

    # 1) Columns present
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        issues.append(f"Missing columns: {', '.join(missing)}")

    if not df.empty:
        # 2) Types and basic ranges
        bad_qty = df.loc[pd.to_numeric(df["Qty"], errors="coerce").fillna(-1) <= 0]
        if not bad_qty.empty:
            issues.append(f"{len(bad_qty)} rows have non-positive Qty")

        # 3) UPC format + check digit
        upc_series = df["UPC"].astype(str).str.replace(r"\D","", regex=True)
        bad_upc = df.loc[~upc_series.map(_upc_ok)]
        if not bad_upc.empty:
            issues.append(f"{len(bad_upc)} rows fail UPC-A check digit")

        # 4) Arithmetic integrity: |Qty*Rate - Amount| <= 0.01
        q = pd.to_numeric(df["Qty"], errors="coerce").fillna(0)
        r = df["Rate"].astype(str).map(_to_money)
        a = df["Amount"].astype(str).map(_to_money)
        bad_amt = (q*r - a).abs() > 0.01
        n_bad = int(bad_amt.sum())
        if n_bad:
            issues.append(f"{n_bad} rows where Qty*Rate != Amount")

        # 5) PO grand total reconciliation (if present in meta)
        if str(meta.get("total","")).strip() not in ("","N/A", "None"):
            target = _to_money(meta["total"])
            actual = float(a.sum())
            if abs(actual - target) > 0.01:
                issues.append(f"Grand total mismatch: parsed=${actual:,.2f}, PDF=${target:,.2f}")

    return {"ok": len(issues) == 0, "summary": issues}
