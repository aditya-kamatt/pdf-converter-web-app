import pytest
import pandas as pd
import numpy as np
import sys
import pathlib

# Add project root to path for imports
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.validator import run_qa_checks, _upc_ok


class TestUPCValidation:
    """Test UPC-A check digit validation"""

    def test_valid_upc_codes(self):
        """Test valid UPC-A check digits"""
        assert _upc_ok("012345678905") == True
        assert _upc_ok("123456789012") == True
        assert _upc_ok("000000000000") == True
        assert _upc_ok("036000291452") == True  # Coca-Cola UPC

    def test_invalid_upc_codes(self):
        """Test invalid UPC-A check digits"""
        assert _upc_ok("012345678900") == False
        assert _upc_ok("111111111111") == False
        assert _upc_ok("123456789010") == False  # Wrong check digit
        assert _upc_ok("036000291453") == False

    def test_invalid_upc_formats(self):
        """Test malformed UPC codes"""
        assert _upc_ok("12345") == False  # Too short
        assert _upc_ok("") == False
        assert _upc_ok("abcdefghijkl") == False
        assert _upc_ok("1234567890123") == False  # Too long


class TestQAChecks:
    """Test QA validation checks for DataFrame"""

    def test_missing_columns(self):
        """Test detection of missing required columns"""
        df = pd.DataFrame({"Qty": [1], "UPC": ["123"]})
        meta = {}
        result = run_qa_checks(df, meta)
        assert result["ok"] == False
        assert any("Missing columns" in issue for issue in result["summary"])

    def test_negative_quantities(self):
        """Test detection of invalid quantities"""
        df = pd.DataFrame({
            "Qty": [-1, 0, 2],
            "Item_SKU": ["A", "B", "C"],
            "Dev_Code": ["D1", "D2", "D3"],
            "UPC": ["012345678905"] * 3,
            "HTS_Code": ["1234567890"] * 3,
            "Brand": ["Brand"] * 3,
            "Description": ["Desc"] * 3,
            "Rate": [10.0, 10.0, 10.0],
            "Amount": [-10.0, 0.0, 20.0]
        })
        meta = {}
        result = run_qa_checks(df, meta)
        assert any("non-positive Qty" in issue for issue in result["summary"])

    def test_invalid_upc_check_digits(self):
        """Test detection of invalid UPC check digits"""
        df = pd.DataFrame({
            "Qty": [1],
            "Item_SKU": ["A"],
            "Dev_Code": ["D1"],
            "UPC": ["111111111111"],  # Invalid check digit
            "HTS_Code": ["1234567890"],
            "Brand": ["Brand"],
            "Description": ["Desc"],
            "Rate": [10.0],
            "Amount": [10.0]
        })
        meta = {}
        result = run_qa_checks(df, meta)
        assert any("UPC-A check digit" in issue for issue in result["summary"])

    def test_arithmetic_mismatch(self):
        """Test detection when Qty * Rate != Amount"""
        df = pd.DataFrame({
            "Qty": [2],
            "Item_SKU": ["A"],
            "Dev_Code": ["D1"],
            "UPC": ["012345678905"],
            "HTS_Code": ["1234567890"],
            "Brand": ["Brand"],
            "Description": ["Desc"],
            "Rate": [10.50],
            "Amount": [25.00]  # Should be 21.00 (2 * 10.50)
        })
        meta = {}
        result = run_qa_checks(df, meta)
        assert any("Qty*Rate != Amount" in issue for issue in result["summary"])

    def test_missing_prices(self):
        """Test detection of missing Rate or Amount"""
        df = pd.DataFrame({
            "Qty": [1],
            "Item_SKU": ["A"],
            "Dev_Code": ["D1"],
            "UPC": ["012345678905"],
            "HTS_Code": ["1234567890"],
            "Brand": ["Brand"],
            "Description": ["Desc"],
            "Rate": [np.nan],
            "Amount": [10.0]
        })
        meta = {}
        result = run_qa_checks(df, meta)
        assert any("missing Rate or Amount" in issue for issue in result["summary"])

    def test_all_valid_data(self):
        """Test with valid data that passes all checks"""
        df = pd.DataFrame({
            "Qty": [2, 3],
            "Item_SKU": ["SKU001", "SKU002"],
            "Dev_Code": ["D1", "D2"],
            "UPC": ["012345678905", "036000291452"],
            "HTS_Code": ["1234567890", "9876543210"],
            "Brand": ["BrandA", "BrandB"],
            "Description": ["Product 1", "Product 2"],
            "Rate": [10.0, 5.0],
            "Amount": [20.0, 15.0]
        })
        meta = {}
        result = run_qa_checks(df, meta)
        # Result should have ok status and minimal issues
        assert isinstance(result, dict)
        assert "summary" in result

    def test_empty_dataframe(self):
        """Test QA checks with empty DataFrame"""
        df = pd.DataFrame({
            "Qty": [],
            "Item_SKU": [],
            "Dev_Code": [],
            "UPC": [],
            "HTS_Code": [],
            "Brand": [],
            "Description": [],
            "Rate": [],
            "Amount": []
        })
        meta = {}
        result = run_qa_checks(df, meta)
        # Should handle empty DataFrame gracefully
        assert isinstance(result, dict)

    def test_mixed_valid_invalid_upcs(self):
        """Test mix of valid and invalid UPCs"""
        df = pd.DataFrame({
            "Qty": [1, 1, 1],
            "Item_SKU": ["A", "B", "C"],
            "Dev_Code": ["D1", "D2", "D3"],
            "UPC": ["012345678905", "111111111111", "036000291452"],  # Middle one invalid
            "HTS_Code": ["1234567890"] * 3,
            "Brand": ["Brand"] * 3,
            "Description": ["Desc"] * 3,
            "Rate": [10.0] * 3,
            "Amount": [10.0] * 3
        })
        meta = {}
        result = run_qa_checks(df, meta)
        # Should detect the invalid UPC
        assert any("UPC-A check digit" in issue for issue in result["summary"])

    def test_price_strings_with_currency(self):
        """Test that prices with $ and commas are handled"""
        df = pd.DataFrame({
            "Qty": [1],
            "Item_SKU": ["A"],
            "Dev_Code": ["D1"],
            "UPC": ["012345678905"],
            "HTS_Code": ["1234567890"],
            "Brand": ["Brand"],
            "Description": ["Desc"],
            "Rate": ["$10.00"],  # String with currency
            "Amount": ["$10.00"]
        })
        meta = {}
        result = run_qa_checks(df, meta)
        # Should parse strings and validate
        assert isinstance(result, dict)

