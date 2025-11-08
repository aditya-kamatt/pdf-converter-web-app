import pathlib
import shutil
import re
import sys
from typing import Dict

# Add project root to path for imports
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest

from core.parser import extract_header_meta, extract_table_rows
from excel_io.excel_writer import write_to_excel

IN_DIR = HERE / "inputs"
EXP_DIR = HERE / "expected"

PDFS = sorted(p.name for p in IN_DIR.glob("*.pdf"))

def _clean_strings(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.select_dtypes(include="object").columns:
        df[c] = (
            df[c]
            .astype(str)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
            .replace({"nan": np.nan})
        )
    return df

def _coerce_numerics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        s = df[c]
        if s.dtype == "object":
            s2 = (
                s.astype(str)
                .str.replace("$", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )
            num = pd.to_numeric(s2, errors="coerce")
            df[c] = num
    return df

def _standardise_nulls(df: pd.DataFrame) -> pd.DataFrame:
    return df.replace({None: np.nan, "": np.nan})

def _normalise(df: pd.DataFrame, sort_keys: list[str] | None = None) -> pd.DataFrame:
    df = _clean_strings(df)
    df = _coerce_numerics(df)
    df = _standardise_nulls(df)
    if sort_keys:
        keys = [k for k in sort_keys if k in df.columns]
        if keys:
            df = df.sort_values(keys, kind="mergesort", na_position="last")
    return df.reset_index(drop=True)

def _read_excel_sheets(path: pathlib.Path) -> Dict[str, pd.DataFrame]:
    """
    Read all sheets as object dtype, so we can normalise and coerce ourselves.
    """
    xls = pd.ExcelFile(path)
    out: Dict[str, pd.DataFrame] = {}
    for name in xls.sheet_names:
        out[name] = pd.read_excel(xls, sheet_name=name, dtype="object")
    return out

def _compare_workbooks(got_path: pathlib.Path, exp_path: pathlib.Path, tmp_path: pathlib.Path):
    got = _read_excel_sheets(got_path)
    exp = _read_excel_sheets(exp_path)

    assert set(got.keys()) == set(exp.keys()), f"Sheet sets differ: {set(got)} vs {set(exp)}"

    if "Summary" in got:
        for df in (got["Summary"], exp["Summary"]):
            if "Field" not in df.columns or "Value" not in df.columns:
                raise AssertionError("Summary sheet must have 'Field' and 'Value' columns")
        def drop_processing_date(df):
            mask = ~(df["Field"].astype(str).str.lower().eq("processing date"))
            return df.loc[mask].reset_index(drop=True)
        gsum = _normalise(drop_processing_date(got["Summary"]))
        esum = _normalise(drop_processing_date(exp["Summary"]))
        assert_frame_equal(gsum, esum, check_dtype=False, rtol=1e-6, atol=1e-8)

    if "Orders" in got:
        g = _normalise(got["Orders"], sort_keys=["Item SKU","UPC","Description","Qty","Rate","Amount"])
        e = _normalise(exp["Orders"], sort_keys=["Item SKU","UPC","Description","Qty","Rate","Amount"])
        assert_frame_equal(g, e, check_dtype=False, check_like=True, rtol=1e-6, atol=1e-8)

    if "SizeSheet" in got:
        g = _normalise(got["SizeSheet"], sort_keys=["Product","Item SKU","Dev Code","HTS Code","Brand"])
        e = _normalise(exp["SizeSheet"], sort_keys=["Product","Item SKU","Dev Code","HTS Code","Brand"])
        assert_frame_equal(g, e, check_dtype=False, check_like=True, rtol=1e-6, atol=1e-8)

@pytest.mark.parametrize("pdf_name", PDFS)
def test_pdf_to_excel_matches_golden(tmp_path, pdf_name, update_golden):
    """
    End-to-end golden test:
      PDF -> (meta, rows) -> DataFrame -> write_to_excel() -> compare to expected.
    """
    input_pdf = IN_DIR / pdf_name
    out_xlsx = tmp_path / (pdf_name.replace(".pdf", ".xlsx"))
    # Expected files have "converted_" prefix
    exp_xlsx = EXP_DIR / f"converted_{out_xlsx.name}"

    meta = extract_header_meta(str(input_pdf))     # header fields + counts
    rows = extract_table_rows(str(input_pdf))      # HEADER + data rows
    assert isinstance(rows, list) and len(rows) >= 2, "No item rows extracted"

    header, data_rows = rows[0], rows[1:]
    df = pd.DataFrame(data_rows, columns=header)

    write_to_excel(df, meta, str(out_xlsx))  

    if update_golden:
        EXP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_xlsx, exp_xlsx)
        pytest.skip(f"Golden updated for {pdf_name}")

    _compare_workbooks(out_xlsx, exp_xlsx, tmp_path)




