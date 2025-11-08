import pytest
import io
import os
import sys
import pathlib

# Add project root to path for imports
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestConvertEndpointErrors:
    """Test error handling in /convert endpoint"""

    def test_no_file_in_request(self, client):
        """Test /convert when no file is uploaded"""
        response = client.post("/convert", data={})
        assert response.status_code == 302  # Redirects back to index

    def test_empty_filename(self, client):
        """Test /convert with empty filename"""
        data = {"file": (io.BytesIO(b"test"), "")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_invalid_file_extension(self, client):
        """Test /convert with non-PDF file"""
        data = {"file": (io.BytesIO(b"test"), "test.txt")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_invalid_doc_extension(self, client):
        """Test /convert with .doc file"""
        data = {"file": (io.BytesIO(b"test"), "document.doc")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_invalid_docx_extension(self, client):
        """Test /convert with .docx file"""
        data = {"file": (io.BytesIO(b"test"), "document.docx")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_pdf_extraction_fails(self, client, monkeypatch, pdf_file):
        """Test /convert when PDF extraction throws error"""
        def failing_extract(path):
            raise ValueError("Cannot parse PDF")

        monkeypatch.setattr("app.extract_data_from_pdf", failing_extract)
        data = {"file": (pdf_file, "test.pdf")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_pdf_extraction_no_rows(self, client, monkeypatch, pdf_file):
        """Test /convert when PDF has no extractable data"""
        def empty_extract(path):
            raise ValueError("No data rows found in PDF")

        monkeypatch.setattr("app.extract_data_from_pdf", empty_extract)
        data = {"file": (pdf_file, "empty.pdf")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302

    def test_excel_writer_fails(self, client, monkeypatch, pdf_file, happy_extract):
        """Test /convert when Excel writing fails"""
        def boom(df, meta, path):
            raise IOError("Cannot write file")

        monkeypatch.setattr("app.write_to_excel", boom)
        data = {"file": (pdf_file, "test.pdf")}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 302


class TestAPIEndpointErrors:
    """Test error handling in /api/convert endpoint"""

    def test_api_no_file(self, client):
        """Test /api/convert with no file"""
        response = client.post("/api/convert", data={})
        assert response.status_code == 400
        json_data = response.get_json()
        assert "error" in json_data
        assert "No file uploaded" in json_data["error"]

    def test_api_empty_filename(self, client):
        """Test /api/convert with empty filename"""
        data = {"file": (io.BytesIO(b"test"), "")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 400
        json_data = response.get_json()
        assert "error" in json_data

    def test_api_invalid_extension(self, client):
        """Test /api/convert with non-PDF"""
        data = {"file": (io.BytesIO(b"test"), "test.doc")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 400
        json_data = response.get_json()
        assert "error" in json_data
        assert "PDF" in json_data["error"]

    def test_api_conversion_error(self, client, monkeypatch, pdf_file):
        """Test /api/convert when conversion fails"""
        def boom(path):
            raise RuntimeError("Processing failed")

        monkeypatch.setattr("app.extract_data_from_pdf", boom)
        data = {"file": (pdf_file, "test.pdf")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 500
        json_data = response.get_json()
        assert "error" in json_data

    def test_api_extraction_value_error(self, client, monkeypatch, pdf_file):
        """Test /api/convert with extraction ValueError"""
        def fail_extract(path):
            raise ValueError("No tables found")

        monkeypatch.setattr("app.extract_data_from_pdf", fail_extract)
        data = {"file": (pdf_file, "bad.pdf")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        assert response.status_code == 500


class TestDownloadEndpoint:
    """Test /download endpoint"""

    def test_download_file_not_found(self, client):
        """Test /download with non-existent file"""
        response = client.get("/download/nonexistent.xlsx")
        assert response.status_code == 404
        json_data = response.get_json()
        assert "error" in json_data
        assert "not found" in json_data["error"].lower()

    def test_download_with_path_traversal(self, client):
        """Test /download with path traversal attempt"""
        response = client.get("/download/../../../etc/passwd")
        # Should either return 404 or redirect (302) due to error handler
        assert response.status_code in [302, 404]

    def test_download_missing_file_different_name(self, client):
        """Test /download with another non-existent filename"""
        response = client.get("/download/missing_file_12345.xlsx")
        assert response.status_code == 404


class TestHelperFunctions:
    """Test helper functions in app module"""

    def test_allowed_file_valid_pdf(self, app_module):
        """Test allowed_file with valid PDF extensions"""
        assert app_module.allowed_file("test.pdf") == True
        assert app_module.allowed_file("test.PDF") == True
        assert app_module.allowed_file("my.file.pdf") == True
        assert app_module.allowed_file("document.with.dots.pdf") == True

    def test_allowed_file_invalid_extensions(self, app_module):
        """Test allowed_file with invalid extensions"""
        assert app_module.allowed_file("test.txt") == False
        assert app_module.allowed_file("test.doc") == False
        assert app_module.allowed_file("test.docx") == False
        assert app_module.allowed_file("test.xls") == False
        assert app_module.allowed_file("test.xlsx") == False

    def test_allowed_file_no_extension(self, app_module):
        """Test allowed_file with no extension"""
        assert app_module.allowed_file("test") == False
        assert app_module.allowed_file("") == False

    def test_allowed_file_only_dot(self, app_module):
        """Test allowed_file with only a dot"""
        assert app_module.allowed_file(".") == False
        assert app_module.allowed_file("..") == False

    def test_extract_data_from_pdf_success(self, app_module, monkeypatch):
        """Test extract_data_from_pdf with successful extraction"""
        def mock_header_meta(path):
            return {"po_number": "12345", "total": "$100.00"}

        def mock_table_rows(path):
            return [
                ["Col1", "Col2", "Col3"],
                ["A", "B", "C"],
                ["D", "E", "F"]
            ]

        monkeypatch.setattr(app_module, "extract_header_meta", mock_header_meta)
        monkeypatch.setattr(app_module, "extract_table_rows", mock_table_rows)

        meta, df = app_module.extract_data_from_pdf("test.pdf")
        assert meta["po_number"] == "12345"
        assert len(df) == 2
        assert list(df.columns) == ["Col1", "Col2", "Col3"]

    def test_extract_data_from_pdf_no_rows(self, app_module, monkeypatch):
        """Test extract_data_from_pdf when no rows extracted"""
        def mock_header_meta(path):
            return {}

        def mock_table_rows(path):
            return []  # Empty

        monkeypatch.setattr(app_module, "extract_header_meta", mock_header_meta)
        monkeypatch.setattr(app_module, "extract_table_rows", mock_table_rows)

        with pytest.raises(ValueError, match="No data rows found"):
            app_module.extract_data_from_pdf("test.pdf")

    def test_extract_data_from_pdf_only_header(self, app_module, monkeypatch):
        """Test extract_data_from_pdf with only header, no data"""
        def mock_header_meta(path):
            return {}

        def mock_table_rows(path):
            return [["Col1", "Col2"]]  # Only header

        monkeypatch.setattr(app_module, "extract_header_meta", mock_header_meta)
        monkeypatch.setattr(app_module, "extract_table_rows", mock_table_rows)

        with pytest.raises(ValueError, match="No data rows found"):
            app_module.extract_data_from_pdf("test.pdf")


class TestHealthEndpoint:
    """Test /health endpoint"""

    def test_health_check_returns_200(self, client):
        """Test /health returns 200"""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_check_has_status(self, client):
        """Test /health includes status field"""
        response = client.get("/health")
        data = response.get_json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_check_has_timestamp(self, client):
        """Test /health includes timestamp"""
        response = client.get("/health")
        data = response.get_json()
        assert "timestamp" in data

    def test_health_check_has_version(self, client):
        """Test /health includes version"""
        response = client.get("/health")
        data = response.get_json()
        assert "version" in data


class TestIndexEndpoint:
    """Test / (index) endpoint"""

    def test_index_returns_200(self, client):
        """Test index page loads"""
        response = client.get("/")
        assert response.status_code == 200

    def test_index_contains_template(self, client):
        """Test index page uses correct template"""
        response = client.get("/")
        body = response.data.decode('utf-8')
        assert "TEMPLATE:index.html" in body

