"""
Integration tests for full end-to-end workflows.

These tests verify the complete user journey from upload through download,
using real PDFs and checking file system state.
"""
import io
import os
import pytest
import sys
import pathlib

# Add project root to path for imports
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestEndToEndWebWorkflow:
    """Test complete web upload → process → download workflow"""

    def test_complete_conversion_workflow_web(self, client, app_module, real_pdf_fixture):
        """
        Test full workflow: upload PDF via web form → conversion → download Excel
        """
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Step 1: Upload and convert via web form
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/convert", data=data, content_type="multipart/form-data")
        
        # Should get Excel file back directly
        assert response.status_code == 200
        assert response.headers["Content-Type"].startswith("application/vnd.openxmlformats")
        assert len(response.data) > 0
        
        # Verify Excel file structure
        import pandas as pd
        from io import BytesIO
        excel_data = BytesIO(response.data)
        
        # Check that we can read the Excel file
        excel_file = pd.ExcelFile(excel_data)
        assert "Summary" in excel_file.sheet_names
        assert "Orders" in excel_file.sheet_names
        
        # Verify Summary sheet has data
        summary_df = pd.read_excel(excel_file, sheet_name="Summary")
        assert len(summary_df) > 0
        
        # Verify Orders sheet has data
        orders_df = pd.read_excel(excel_file, sheet_name="Orders")
        assert len(orders_df) > 0

    def test_complete_conversion_workflow_api(self, client, app_module, real_pdf_fixture):
        """
        Test full workflow: upload PDF via API → get download URL → download Excel
        """
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Step 1: Upload and convert via API
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert "download_url" in json_data
        assert json_data["rows_processed"] > 0
        
        # Step 2: Download the converted file
        download_url = json_data["download_url"]
        download_response = client.get(download_url)
        
        assert download_response.status_code == 200
        assert download_response.headers["Content-Type"].startswith("application/vnd.openxmlformats")
        assert len(download_response.data) > 0
        
        # Step 3: Verify file exists in output folder
        filename = download_url.split("/")[-1]
        output_path = os.path.join(app_module.OUTPUT_FOLDER, filename)
        assert os.path.exists(output_path)
        
        # Step 4: Verify Excel structure
        import pandas as pd
        excel_file = pd.ExcelFile(output_path)
        assert "Summary" in excel_file.sheet_names
        assert "Orders" in excel_file.sheet_names

    def test_concurrent_conversions(self, client, app_module, real_pdf_fixture):
        """
        Test multiple concurrent API requests don't interfere with each other
        """
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Simulate 5 concurrent uploads
        results = []
        for i in range(5):
            data = {"file": (io.BytesIO(pdf_data), f"test_{i}_{pdf_name}")}
            response = client.post("/api/convert", data=data, content_type="multipart/form-data")
            results.append(response)
        
        # All should succeed
        for response in results:
            assert response.status_code == 200
            json_data = response.get_json()
            assert json_data["success"] is True
        
        # All should have unique download URLs
        download_urls = [r.get_json()["download_url"] for r in results]
        assert len(set(download_urls)) == 5

    def test_file_cleanup_after_upload(self, client, app_module, real_pdf_fixture):
        """
        Test that uploaded PDF is cleaned up after conversion
        """
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Get initial file count in upload folder
        initial_uploads = len(os.listdir(app_module.UPLOAD_FOLDER))
        
        # Upload and convert
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        assert response.status_code == 200
        
        # Upload folder should be cleaned (file removed after processing)
        final_uploads = len(os.listdir(app_module.UPLOAD_FOLDER))
        assert final_uploads == initial_uploads  # Should be back to initial count

    def test_invalid_pdf_handling(self, client):
        """
        Test handling of corrupted/invalid PDF files
        """
        # Create a fake "PDF" that's not actually a valid PDF
        fake_pdf = b"This is not a real PDF file"
        
        data = {"file": (io.BytesIO(fake_pdf), "fake.pdf")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        # Should return error
        assert response.status_code == 500
        json_data = response.get_json()
        assert "error" in json_data

    def test_large_pdf_handling(self, client, app_module):
        """
        Test handling of large PDF files (near the size limit)
        """
        # Create a PDF-like file that's close to the 16MB limit (15MB)
        large_data = b"%PDF-1.4\n" + (b"X" * (15 * 1024 * 1024))
        
        data = {"file": (io.BytesIO(large_data), "large.pdf")}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        # Should either process or return a reasonable error (not crash)
        assert response.status_code in [200, 500]
        if response.status_code == 500:
            json_data = response.get_json()
            assert "error" in json_data


class TestFileSystemState:
    """Test that file system state is managed correctly"""

    def test_output_folder_created_on_startup(self, app_module):
        """Test that output folder exists"""
        assert os.path.exists(app_module.OUTPUT_FOLDER)
        assert os.path.isdir(app_module.OUTPUT_FOLDER)

    def test_upload_folder_created_on_startup(self, app_module):
        """Test that upload folder exists"""
        assert os.path.exists(app_module.UPLOAD_FOLDER)
        assert os.path.isdir(app_module.UPLOAD_FOLDER)

    def test_converted_files_persist_in_output(self, client, app_module, real_pdf_fixture):
        """Test that converted Excel files remain in output folder"""
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Convert file
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        assert response.status_code == 200
        json_data = response.get_json()
        download_url = json_data["download_url"]
        filename = download_url.split("/")[-1]
        
        # File should exist
        output_path = os.path.join(app_module.OUTPUT_FOLDER, filename)
        assert os.path.exists(output_path)
        assert os.path.getsize(output_path) > 0

    def test_cleanup_old_files_functionality(self, app_module, tmp_path):
        """Test that cleanup_old_files removes old files correctly"""
        import time
        
        # Create test files
        old_upload = os.path.join(app_module.UPLOAD_FOLDER, "old_upload.pdf")
        old_output = os.path.join(app_module.OUTPUT_FOLDER, "old_output.xlsx")
        new_upload = os.path.join(app_module.UPLOAD_FOLDER, "new_upload.pdf")
        
        # Create files
        with open(old_upload, 'wb') as f:
            f.write(b"old")
        with open(old_output, 'wb') as f:
            f.write(b"old")
        with open(new_upload, 'wb') as f:
            f.write(b"new")
        
        # Set old timestamps on files using os.utime (2 hours ago)
        old_time = time.time() - (2 * 3600)
        os.utime(old_upload, (old_time, old_time))
        os.utime(old_output, (old_time, old_time))
        
        # Run cleanup with 1 hour threshold
        app_module.cleanup_old_files(hours=1)
        
        # Old files should be removed, new file should remain
        assert not os.path.exists(old_upload)
        assert not os.path.exists(old_output)
        assert os.path.exists(new_upload)


class TestMetadataExtraction:
    """Test that metadata is correctly extracted and returned"""

    def test_metadata_in_api_response(self, client, real_pdf_fixture):
        """Test that API response includes extracted metadata"""
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        assert response.status_code == 200
        json_data = response.get_json()
        
        # Should have metadata field
        assert "metadata" in json_data
        metadata = json_data["metadata"]
        
        # Should have expected metadata keys
        assert "po_number" in metadata
        assert "vendor_number" in metadata
        assert "ship_by_date" in metadata
        assert "payment_terms" in metadata
        assert "total" in metadata
        assert "page_count" in metadata

    def test_rows_processed_count(self, client, real_pdf_fixture):
        """Test that rows_processed count is accurate"""
        pdf_path, pdf_name = real_pdf_fixture
        
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        data = {"file": (io.BytesIO(pdf_data), pdf_name)}
        response = client.post("/api/convert", data=data, content_type="multipart/form-data")
        
        assert response.status_code == 200
        json_data = response.get_json()
        
        # Should have positive row count
        assert json_data["rows_processed"] > 0
        
        # Verify against actual Excel file
        download_url = json_data["download_url"]
        filename = download_url.split("/")[-1]
        
        import pandas as pd
        import os
        from app import OUTPUT_FOLDER
        output_path = os.path.join(OUTPUT_FOLDER, filename)
        
        orders_df = pd.read_excel(output_path, sheet_name="Orders")
        assert len(orders_df) == json_data["rows_processed"]

