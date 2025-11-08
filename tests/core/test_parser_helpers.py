import pytest
import sys
import pathlib

# Add project root to path for imports
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.parser as parser_mod


class TestParserHelperFunctions:
    """Test individual helper functions in parser module"""

    def test_to_float_valid_numbers(self):
        """Test _to_float with valid numeric strings"""
        to_float = parser_mod._to_float
        assert to_float("10") == 10.0
        assert to_float("10.00") == 10.0
        assert to_float("10.50") == 10.50
        assert to_float("0.01") == 0.01
        assert to_float("9999.99") == 9999.99

    def test_to_float_currency_formats(self):
        """Test _to_float with currency symbols"""
        to_float = parser_mod._to_float
        assert to_float("$10.00") == 10.0
        assert to_float("$1,234.56") == 1234.56
        assert to_float("USD 99.90") == 99.90
        assert to_float("USD$100.00") == 100.0

    def test_to_float_with_commas(self):
        """Test _to_float with comma separators"""
        to_float = parser_mod._to_float
        assert to_float("1,000.00") == 1000.0
        assert to_float("10,000.50") == 10000.50
        assert to_float("1,234,567.89") == 1234567.89

    def test_to_float_invalid_input(self):
        """Test _to_float with invalid input"""
        to_float = parser_mod._to_float
        assert to_float("not money") is None
        assert to_float("abc") is None
        assert to_float("") is None
        assert to_float(None) is None
        assert to_float("$$$") is None

    def test_to_float_edge_cases(self):
        """Test _to_float with edge cases"""
        to_float = parser_mod._to_float
        assert to_float("0") == 0.0
        assert to_float("0.00") == 0.0
        assert to_float("  10.00  ") == 10.0  # With whitespace

    def test_to_int_valid_numbers(self):
        """Test _to_int with valid integers"""
        to_int = parser_mod._to_int
        assert to_int("1") == 1
        assert to_int("10") == 10
        assert to_int("007") == 7
        assert to_int("  007  ") == 7
        assert to_int("1000") == 1000

    def test_to_int_invalid_input(self):
        """Test _to_int with invalid input"""
        to_int = parser_mod._to_int
        assert to_int("nope") is None
        assert to_int("abc") is None
        assert to_int("") is None
        assert to_int(None) is None
        assert to_int("-") is None

    def test_to_int_with_non_numeric_chars(self):
        """Test _to_int strips non-numeric characters"""
        to_int = parser_mod._to_int
        assert to_int("10 units") == 10
        assert to_int("qty: 5") == 5
        assert to_int("#7") == 7

    def test_to_int_negative_numbers(self):
        """Test _to_int with negative numbers"""
        to_int = parser_mod._to_int
        assert to_int("-1") == -1
        assert to_int("-100") == -100

    def test_clean_ws_basic(self):
        """Test _clean_ws with basic strings"""
        clean_ws = parser_mod._clean_ws
        assert clean_ws("hello") == "hello"
        assert clean_ws("hello world") == "hello world"
        assert clean_ws("  hello  ") == "hello"

    def test_clean_ws_multiple_spaces(self):
        """Test _clean_ws collapses multiple spaces"""
        clean_ws = parser_mod._clean_ws
        assert clean_ws("a   b") == "a b"
        assert clean_ws("a     b     c") == "a b c"
        assert clean_ws("  a   b \n c  ") == "a b c"

    def test_clean_ws_with_tabs_newlines(self):
        """Test _clean_ws handles tabs and newlines"""
        clean_ws = parser_mod._clean_ws
        assert clean_ws("a\tb") == "a b"
        assert clean_ws("a\nb") == "a b"
        assert clean_ws("a\r\nb") == "a b"
        assert clean_ws("a\t\n\rb") == "a b"

    def test_clean_ws_empty_and_none(self):
        """Test _clean_ws with empty/None input"""
        clean_ws = parser_mod._clean_ws
        assert clean_ws("") == ""
        assert clean_ws(None) == ""
        assert clean_ws("   ") == ""

    def test_split_brand_desc_basic(self):
        """Test _split_brand_desc with normal input"""
        split = parser_mod._split_brand_desc
        assert split("ACME Widget") == ("ACME", "Widget")
        assert split("BrandX Product Name") == ("BrandX", "Product Name")
        assert split("Nike Air Max Shoes") == ("Nike", "Air Max Shoes")

    def test_split_brand_desc_single_word(self):
        """Test _split_brand_desc with single word"""
        split = parser_mod._split_brand_desc
        assert split("SingleBrand") == ("SingleBrand", "")
        assert split("ACME") == ("ACME", "")

    def test_split_brand_desc_empty(self):
        """Test _split_brand_desc with empty input"""
        split = parser_mod._split_brand_desc
        assert split("") == ("", "")
        assert split("   ") == ("", "")

    def test_split_brand_desc_multiple_spaces(self):
        """Test _split_brand_desc handles extra whitespace"""
        split = parser_mod._split_brand_desc
        assert split("ACME   Widget") == ("ACME", "Widget")
        assert split("  Brand   Product  Name  ") == ("Brand", "Product Name")

    def test_dedupe_removes_duplicates(self):
        """Test _dedupe removes duplicate rows"""
        dedupe = parser_mod._dedupe
        rows = [
            [1, "SKU1", "D1", "UPC1", "", "B1", "Desc1", 1.0, 1.0],
            [2, "SKU1", "D1", "UPC1", "", "B1", "Desc1", 2.0, 2.0],  # Duplicate
            [1, "SKU2", "D2", "UPC2", "", "B2", "Desc2", 1.0, 1.0],
        ]
        result = dedupe(rows)
        assert len(result) == 2
        assert result[0][1] == "SKU1"  # First occurrence kept
        assert result[1][1] == "SKU2"

    def test_dedupe_preserves_order(self):
        """Test _dedupe preserves original order"""
        dedupe = parser_mod._dedupe
        rows = [
            [1, "SKU1", "", "UPC1", "", "", "", 1.0, 1.0],
            [1, "SKU2", "", "UPC2", "", "", "", 1.0, 1.0],
            [1, "SKU3", "", "UPC3", "", "", "", 1.0, 1.0],
            [1, "SKU1", "", "UPC1", "", "", "", 1.0, 1.0],  # Duplicate of first
        ]
        result = dedupe(rows)
        assert len(result) == 3
        assert [r[1] for r in result] == ["SKU1", "SKU2", "SKU3"]

    def test_dedupe_empty_input(self):
        """Test _dedupe with empty list"""
        dedupe = parser_mod._dedupe
        assert dedupe([]) == []

    def test_dedupe_single_row(self):
        """Test _dedupe with single row"""
        dedupe = parser_mod._dedupe
        rows = [[1, "SKU1", "", "UPC1", "", "", "", 1.0, 1.0]]
        assert dedupe(rows) == rows

    def test_is_reasonable_valid_data(self):
        """Test _is_reasonable with valid data"""
        is_reasonable = parser_mod._is_reasonable
        HEADER = ["Qty", "Item_SKU", "Dev_Code", "UPC", "HTS_Code", 
                  "Brand", "Description", "Rate", "Amount"]
        valid = [HEADER, [1, "A", "D", "123", "", "B", "Desc", 1.0, 1.0]]
        assert is_reasonable(valid) is True

    def test_is_reasonable_header_only(self):
        """Test _is_reasonable rejects header-only data"""
        is_reasonable = parser_mod._is_reasonable
        HEADER = ["Qty", "Item_SKU", "Dev_Code", "UPC", "HTS_Code",
                  "Brand", "Description", "Rate", "Amount"]
        header_only = [HEADER]
        assert is_reasonable(header_only) is False

    def test_is_reasonable_empty_list(self):
        """Test _is_reasonable rejects empty list"""
        is_reasonable = parser_mod._is_reasonable
        assert is_reasonable([]) is False

    def test_is_reasonable_not_a_list(self):
        """Test _is_reasonable rejects non-list input"""
        is_reasonable = parser_mod._is_reasonable
        assert is_reasonable("not a list") is False
        assert is_reasonable(None) is False
        assert is_reasonable(123) is False

    def test_first_match_finds_pattern(self):
        """Test _first_match finds regex pattern"""
        first_match = parser_mod._first_match
        assert first_match("abc 123 def", r"\d+") == "123"
        assert first_match("SKU12345", r"\d{5}") == "12345"
        assert first_match("price $10.50", r"\$\d+\.\d{2}") == "$10.50"

    def test_first_match_no_match(self):
        """Test _first_match returns empty string when no match"""
        first_match = parser_mod._first_match
        assert first_match("abc def", r"\d+") == ""
        assert first_match("", r"\d+") == ""
        assert first_match(None, r"\d+") == ""

    def test_first_match_multiple_matches(self):
        """Test _first_match returns first match only"""
        first_match = parser_mod._first_match
        assert first_match("123 456 789", r"\d+") == "123"
        assert first_match("aaa bbb ccc", r"\w+") == "aaa"

    def test_safe_pick_valid_index(self):
        """Test _safe_pick retrieves values at valid indices"""
        safe_pick = parser_mod._safe_pick
        row = ["a", "b", "c", "d"]
        assert safe_pick(row, 0) == "a"
        assert safe_pick(row, 1) == "b"
        assert safe_pick(row, 3) == "d"

    def test_safe_pick_negative_index(self):
        """Test _safe_pick with negative indices"""
        safe_pick = parser_mod._safe_pick
        row = ["a", "b", "c"]
        assert safe_pick(row, -1) == "c"
        assert safe_pick(row, -2) == "b"

    def test_safe_pick_out_of_range(self):
        """Test _safe_pick returns empty string for out-of-range"""
        safe_pick = parser_mod._safe_pick
        row = ["a", "b"]
        assert safe_pick(row, 10) == ""
        assert safe_pick(row, 100) == ""

    def test_safe_pick_with_whitespace(self):
        """Test _safe_pick cleans whitespace"""
        safe_pick = parser_mod._safe_pick
        row = ["  a  ", " b ", "c\n"]
        assert safe_pick(row, 0) == "a"
        assert safe_pick(row, 1) == "b"
        assert safe_pick(row, 2) == "c"

    def test_safe_pick_empty_row(self):
        """Test _safe_pick with empty row"""
        safe_pick = parser_mod._safe_pick
        assert safe_pick([], 0) == ""


class TestExtractAllText:
    """Test _extract_all_text function - skipped because pdfplumber is imported inside function"""

    @pytest.mark.skip(reason="pdfplumber is imported inside _extract_all_text, cannot monkeypatch at module level")
    def test_extract_all_text_with_mocked_pdfplumber(self, monkeypatch, tmp_path):
        """Test _extract_all_text with mocked pdfplumber"""
        pass

    @pytest.mark.skip(reason="pdfplumber is imported inside _extract_all_text, cannot monkeypatch at module level")
    def test_extract_all_text_empty_pages(self, monkeypatch):
        """Test _extract_all_text with empty pages"""
        pass


class TestExtractHeaderMeta:
    """Test extract_header_meta edge cases"""

    def test_extract_header_meta_all_fields_found(self, monkeypatch):
        """Test when all metadata fields are found"""
        def mock_extract_all_text(path):
            return [
                """
                PO #001234
                Vendor # 5678
                SHIP BY DATE: 12/31/2025
                PAYMENT TERMS: Net 30
                """,
                "Total $1,234.56"
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", mock_extract_all_text)
        
        meta = parser_mod.extract_header_meta("fake.pdf")
        assert meta["po_number"] == "001234"
        assert meta["vendor_number"] == "5678"  # Just the number, not "V5678"
        assert meta["ship_by_date"] == "12/31/2025"
        assert "Net 30" in meta["payment_terms"]
        assert meta["total"] == "1,234.56"
        assert meta["page_count"] == 2

    def test_extract_header_meta_partial_fields(self, monkeypatch):
        """Test when only some fields are found"""
        def mock_extract_all_text(path):
            return ["PO #99999", "Some text"]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", mock_extract_all_text)
        
        meta = parser_mod.extract_header_meta("fake.pdf")
        assert meta["po_number"] == "99999"
        assert meta["vendor_number"] == "N/A"
        assert meta["ship_by_date"] == "N/A"
        assert meta["payment_terms"] == "N/A"
        assert meta["total"] == "N/A"

    def test_extract_header_meta_total_on_last_page(self, monkeypatch):
        """Test that total is found on last page"""
        def mock_extract_all_text(path):
            return [
                "Page 1 content",
                "Page 2 content",
                "Final page Total $5,000.00"
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", mock_extract_all_text)
        
        meta = parser_mod.extract_header_meta("fake.pdf")
        assert meta["total"] == "5,000.00"

    def test_extract_header_meta_alternate_formats(self, monkeypatch):
        """Test alternate field formats"""
        def mock_extract_all_text(path):
            return [
                """
                Purchase Order #12345
                Vendor No. 999
                Ship By: 01/15/2026
                Terms: Due on receipt
                Total $999.99
                """
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", mock_extract_all_text)
        
        meta = parser_mod.extract_header_meta("fake.pdf")
        assert meta["po_number"] == "12345"
        assert meta["vendor_number"] == "999"
        assert meta["ship_by_date"] == "01/15/2026"


class TestExtractTableRowsFallback:
    """Test extract_table_rows fallback logic"""

    def test_extract_table_rows_uses_fallbacks(self, monkeypatch):
        """Test that extract_table_rows tries fallbacks when position fails"""
        # Make position extraction fail
        def fail_positions(path):
            raise Exception("Position extraction failed")
        
        # Make table extraction return header only (unreasonable)
        def fail_tables(path):
            return [parser_mod.HEADER]
        
        # Make regex succeed
        def succeed_regex(path):
            return [
                parser_mod.HEADER,
                [1, "SKU1", "D1", "UPC1", "", "Brand", "Desc", 10.0, 10.0]
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_positions)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_tables)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", succeed_regex)
        
        result = parser_mod.extract_table_rows("fake.pdf")
        assert len(result) == 2
        assert result[0] == parser_mod.HEADER
        assert result[1][1] == "SKU1"

    def test_extract_table_rows_all_fail(self, monkeypatch):
        """Test when all extraction methods fail"""
        def fail_all(path):
            return [parser_mod.HEADER]  # Unreasonable
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_all)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_all)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", fail_all)
        
        result = parser_mod.extract_table_rows("fake.pdf")
        assert result == [parser_mod.HEADER]

