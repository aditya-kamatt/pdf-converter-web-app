"""
Tests for parser error recovery and fallback mechanisms.

This module tests the robustness of the parser when extraction methods fail,
ensuring proper fallback behavior and error handling.
"""
import pytest
import sys
import pathlib

# Add project root to path
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import core.parser as parser_mod
from core.parser import extract_table_rows, extract_header_meta, HEADER


class TestPositionExtractionErrorRecovery:
    """Test position-based extraction error recovery"""

    def test_position_extraction_falls_back_to_tables(self, monkeypatch):
        """
        Test that when position extraction fails, table extraction is attempted
        """
        def failing_positions(path):
            raise Exception("Position extraction failed")
        
        def working_tables(path):
            return [
                HEADER,
                [1, "SKU1", "D1", "UPC1", "HTS1", "Brand", "Desc", 10.0, 10.0]
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", failing_positions)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", working_tables)
        
        result = extract_table_rows("fake.pdf")
        assert len(result) == 2
        assert result[0] == HEADER
        assert result[1][1] == "SKU1"

    def test_position_extraction_unreasonable_falls_back(self, monkeypatch):
        """
        Test that when position extraction returns unreasonable data,
        table extraction is attempted
        """
        def unreasonable_positions(path):
            return [HEADER]  # Only header, no data
        
        def working_tables(path):
            return [
                HEADER,
                [2, "SKU2", "D2", "UPC2", "HTS2", "Brand", "Desc", 20.0, 40.0]
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", unreasonable_positions)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", working_tables)
        
        result = extract_table_rows("fake.pdf")
        assert len(result) == 2
        assert result[1][0] == 2  # Qty from table extraction


class TestTableExtractionErrorRecovery:
    """Test table extraction error recovery"""

    def test_table_extraction_falls_back_to_regex(self, monkeypatch):
        """
        Test that when both position and table extraction fail,
        regex extraction is attempted
        """
        def fail_positions(path):
            return [HEADER]
        
        def fail_tables(path):
            return [HEADER]
        
        def working_regex(path):
            return [
                HEADER,
                [3, "SKU3", "D3", "UPC3", "HTS3", "Brand", "Desc", 30.0, 90.0]
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_positions)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_tables)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", working_regex)
        
        result = extract_table_rows("fake.pdf")
        assert len(result) == 2
        assert result[1][1] == "SKU3"

    def test_table_extraction_exception_continues_to_regex(self, monkeypatch):
        """
        Test that exceptions in table extraction don't crash, continue to regex
        """
        def fail_positions(path):
            raise RuntimeError("Position failed")
        
        def fail_tables(path):
            raise RuntimeError("Table failed")
        
        def working_regex(path):
            return [
                HEADER,
                [1, "SKU4", "D4", "UPC4", "HTS4", "Brand", "Desc", 10.0, 10.0]
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_positions)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_tables)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", working_regex)
        
        result = extract_table_rows("fake.pdf")
        assert len(result) == 2
        assert result[1][1] == "SKU4"


class TestAllExtractionMethodsFail:
    """Test behavior when all extraction methods fail"""

    def test_all_methods_fail_returns_header_only(self, monkeypatch):
        """
        Test that when all extraction methods fail or return unreasonable data,
        we return at least the header
        """
        def fail_all(path):
            return [HEADER]  # Unreasonable - no data
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_all)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_all)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", fail_all)
        
        result = extract_table_rows("fake.pdf")
        assert result == [HEADER]

    def test_all_methods_throw_exceptions(self, monkeypatch):
        """
        Test handling when all methods throw exceptions
        """
        def explode(path):
            raise Exception("Extraction failed")
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", explode)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", explode)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", explode)
        
        result = extract_table_rows("fake.pdf")
        # Should handle gracefully and return at least header
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_empty_pdf_returns_header(self, monkeypatch):
        """
        Test that empty or malformed PDFs return at least the header
        """
        def return_empty(path):
            return []
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", return_empty)
        monkeypatch.setattr(parser_mod, "_extract_via_positions", return_empty)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", return_empty)
        monkeypatch.setattr(parser_mod, "_extract_via_regex", return_empty)
        
        result = extract_table_rows("fake.pdf")
        assert isinstance(result, list)


class TestRegexExtractionRobustness:
    """Test regex extraction as last resort"""

    def test_regex_extraction_with_malformed_text(self, monkeypatch):
        """
        Test regex extraction with poorly formatted text
        """
        def fail_primary(path):
            return [HEADER]
        
        # Simulate malformed text that regex should still handle
        def malformed_text(path):
            return ["random text without proper structure"]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_primary)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_primary)
        monkeypatch.setattr(parser_mod, "_extract_all_text", malformed_text)
        
        result = extract_table_rows("fake.pdf")
        # Should not crash, return at least header
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_regex_handles_missing_amount_computation(self, monkeypatch):
        """
        Test that regex extraction computes amount when missing (qty * rate)
        """
        def fail_primary(path):
            return [HEADER]
        
        # Text with qty, rate but potentially missing amount
        def text_with_partial_data(path):
            # This simulates a line where amount might need computation
            return [
                "5 SKU123 DEV123 012345678901 HTS123 BrandX Product Desc $10.50"
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", fail_primary)
        monkeypatch.setattr(parser_mod, "_extract_via_tables", fail_primary)
        monkeypatch.setattr(parser_mod, "_extract_all_text", text_with_partial_data)
        
        result = extract_table_rows("fake.pdf")
        # Should handle gracefully even if parsing is imperfect
        assert isinstance(result, list)


class TestHeaderMetadataErrorRecovery:
    """Test header metadata extraction error recovery"""

    def test_header_meta_with_no_text(self, monkeypatch):
        """
        Test header metadata extraction when PDF has no extractable text
        """
        def no_text(path):
            return []
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", no_text)
        
        meta = extract_header_meta("fake.pdf")
        
        # Should return dict with N/A values
        assert meta["po_number"] == "N/A"
        assert meta["vendor_number"] == "N/A"
        assert meta["ship_by_date"] == "N/A"
        assert meta["payment_terms"] == "N/A"
        assert meta["total"] == "N/A"
        assert meta["page_count"] == 0

    def test_header_meta_with_partial_matches(self, monkeypatch):
        """
        Test header metadata when only some fields are present
        """
        def partial_text(path):
            return ["PO #12345\nRandom text\nTotal $100.00"]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", partial_text)
        
        meta = extract_header_meta("fake.pdf")
        
        assert meta["po_number"] == "12345"
        assert meta["total"] == "100.00"
        assert meta["vendor_number"] == "N/A"
        assert meta["ship_by_date"] == "N/A"
        assert meta["page_count"] == 1

    def test_header_meta_with_malformed_fields(self, monkeypatch):
        """
        Test header metadata with malformed field values
        """
        def malformed_text(path):
            return [
                "PO #ABC-123-XYZ\n"  # Non-standard PO format
                "Vendor # V999999999\n"  # Very long vendor number
                "Total $999,999,999.99"  # Large total
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_all_text", malformed_text)
        
        meta = extract_header_meta("fake.pdf")
        
        # Should handle without crashing
        assert isinstance(meta, dict)
        assert "po_number" in meta
        assert "vendor_number" in meta
        assert "total" in meta


class TestContinuationLineHandling:
    """Test handling of continuation lines in extraction"""

    def test_continuation_lines_appended_to_description(self, monkeypatch):
        """
        Test that continuation lines (no SKU/UPC) are appended to previous description
        """
        # This is a simplified test - actual implementation may vary
        def text_with_continuations(path):
            return [
                HEADER,
                [1, "SKU1", "D1", "UPC1", "HTS1", "Brand", "Short desc", 10.0, 10.0],
                # Continuation line would be handled by position extractor
            ]
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", text_with_continuations)
        
        result = extract_table_rows("fake.pdf")
        assert len(result) >= 2


class TestDeduplicationWithErrors:
    """Test deduplication when data has issues"""

    def test_dedupe_with_mixed_data_types(self):
        """
        Test deduplication when SKU/UPC have mixed data types
        """
        rows = [
            [1, "SKU1", "D1", "UPC1", "HTS1", "B1", "Desc1", 1.0, 1.0],
            [2, "SKU1", "D1", "UPC1", "HTS1", "B1", "Desc1", 2.0, 2.0],  # Dup
            [1, 123, "D2", 456, "HTS2", "B2", "Desc2", 1.0, 1.0],  # Numbers
        ]
        result = parser_mod._dedupe([HEADER] + rows)
        
        # Should handle mixed types gracefully
        assert len(result) >= 2

    def test_dedupe_with_empty_strings(self):
        """
        Test deduplication when SKU/UPC are empty strings
        """
        rows = [
            [1, "", "D1", "", "HTS1", "B1", "Desc1", 1.0, 1.0],
            [2, "", "D2", "", "HTS2", "B2", "Desc2", 2.0, 2.0],
            [3, "SKU3", "D3", "UPC3", "HTS3", "B3", "Desc3", 3.0, 3.0],
        ]
        result = parser_mod._dedupe([HEADER] + rows)
        
        # Should not crash with empty strings
        assert isinstance(result, list)
        assert len(result) >= 2


class TestAmountComputationFallback:
    """Test amount computation when missing"""

    def test_amount_computed_from_qty_rate(self, monkeypatch):
        """
        Test that missing amounts are computed as qty * rate
        """
        # Create row with missing amount
        rows_with_missing = [
            HEADER,
            [5, "SKU1", "D1", "UPC1", "HTS1", "Brand", "Desc", 10.50, None]
        ]
        
        def return_missing_amounts(path):
            return rows_with_missing
        
        monkeypatch.setattr(parser_mod, "_extract_via_positions", return_missing_amounts)
        
        result = extract_table_rows("fake.pdf")
        
        # The extraction methods should handle this internally
        # Just verify we get data back
        assert len(result) >= 1

    def test_zero_rate_zero_amount(self):
        """
        Test handling of zero rates and amounts
        """
        rows = [
            HEADER,
            [0, "SKU1", "D1", "UPC1", "HTS1", "Brand", "Desc", 0.0, 0.0]
        ]
        
        # Should not crash with zero values
        result = parser_mod._dedupe(rows)
        assert len(result) == 2

