import io
import json
import os
import time
import pandas as pd
import pytest

# -------------------------
# Helpers
# -------------------------

def test_allowed_file(app_module):
    assert app_module.allowed_file("x.pdf")
    assert not app_module.allowed_file("x.PDFX")
    assert not app_module.allowed_file("x.txt")
    assert not app_module.allowed_file("noprefix")

def test_cleanup_old_files(app_module, tmp_path, monkeypatch):
    up = tmp_path / "uploads" / "old.tmp"
    out = tmp_path / "outputs" / "old.xlsx"
    up.write_bytes(b"u")
    out.write_bytes(b"o")

    # Make "now" far in the future so files look old
    monkeypatch.setattr(time, "time", lambda: 10**10)
    # ctime will be < cutoff by virtue of earlier file creation time
    app_module.cleanup_old_files(hours=1)

    assert not up.exists()
    assert not out.exists()

# -------------------------
# extract_data_from_pdf
# -------------------------

def test_extract_data_success(app_module, monkeypatch):
    # Mock internals it calls
    monkeypatch.setattr(app_module, "extract_header_meta", lambda p: {"k": "v"})
    monkeypatch.setattr(app_module, "extract_table_rows", lambda p: [["a","b"], [1,2]])
    meta, df = app_module.extract_data_from_pdf("dummy.pdf")
    assert meta == {"k": "v"}
    assert list(df.columns) == ["a", "b"]
    assert df.shape == (1, 2)

def test_extract_data_raises_on_no_rows(app_module, monkeypatch):
    monkeypatch.setattr(app_module, "extract_header_meta", lambda p: {"k": "v"})
    monkeypatch.setattr(app_module, "extract_table_rows", lambda p: [])
    with pytest.raises(ValueError):
        app_module.extract_data_from_pdf("dummy.pdf")

# -------------------------
# /health
# -------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data

# -------------------------
# /api/convert
# -------------------------

def test_api_convert_happy_path(client, app_module, pdf_file, happy_extract, stub_writer):
    data = {"file": (pdf_file, "sample.pdf")}
    r = client.post("/api/convert", data=data, content_type="multipart/form-data")
    assert r.status_code == 200
    payload = r.get_json()
    assert payload["success"] is True
    assert payload["rows_processed"] == 2  # from happy_extract rows
    assert payload["download_url"].startswith("/download/")

def test_api_convert_validation(client):
    # no file
    r = client.post("/api/convert", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    # empty filename
    data = {"file": (io.BytesIO(b"abc"), "")}
    r = client.post("/api/convert", data=data, content_type="multipart/form-data")
    assert r.status_code == 400
    # wrong extension
    data = {"file": (io.BytesIO(b"abc"), "x.txt")}
    r = client.post("/api/convert", data=data, content_type="multipart/form-data")
    assert r.status_code == 400

def test_api_convert_failure(client, app_module, pdf_file, failing_extract):
    data = {"file": (pdf_file, "bad.pdf")}
    r = client.post("/api/convert", data=data, content_type="multipart/form-data")
    assert r.status_code == 500
    assert "error" in r.get_json()

# -------------------------
# /download and /outputs
# -------------------------

def test_download_missing(client):
    r = client.get("/download/missing.xlsx")
    assert r.status_code == 404

def test_download_present(client, app_module, tmp_path):
    fname = "ok.xlsx"
    path = os.path.join(app_module.OUTPUT_FOLDER, fname)
    with open(path, "wb") as f:
        f.write(b"XLSX")
    r = client.get(f"/download/{fname}")
    assert r.status_code == 200
    assert r.headers["Content-Type"].startswith("application/vnd.openxmlformats")

def test_outputs_path_traversal_blocked(client):
    r = client.get("/outputs/../../secret.xlsx")
    assert r.status_code == 400

def test_outputs_not_found(client):
    r = client.get("/outputs/some_job/none.xlsx")
    assert r.status_code == 404

def test_outputs_serves_file(client, app_module, tmp_path):
    job_id = "job123"
    job_dir = os.path.join(app_module.OUTPUT_FOLDER, job_id)
    os.makedirs(job_dir, exist_ok=True)
    xlsx = os.path.join(job_dir, "file.xlsx")
    with open(xlsx, "wb") as f:
        f.write(b"XLSX")
    r = client.get(f"/outputs/{job_id}/file.xlsx")
    assert r.status_code == 200

# -------------------------
# HTML routes: / and /jobs
# -------------------------

def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.data.startswith(b"TEMPLATE:index.html")

def test_jobs_multiple_files(client, app_module, happy_extract, stub_writer):
    # use two PDFs; also add a wrong type to assert per-file error handling
    data = {
        "files": [
            (io.BytesIO(b"%PDF-1"), "a.pdf"),
            (io.BytesIO(b"%PDF-1"), "b.pdf"),
            (io.BytesIO(b"nope"), "c.txt"),
        ]
    }
    r = client.post("/jobs", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert r.status_code == 200

    # the stubbed template returns JSON-able ctx inside the string ; parse a bit:
    body = r.data.decode("utf-8")
    assert "job_results.html" in body  # render target
    # ensure registry was written and job dir exists
    # Extract job_id from ctx dump
    import re, json
    m = re.search(r'CTX:(\{.*\})', body)
    assert m, "Template ctx missing"
    ctx = json.loads(m.group(1))
    job_id = ctx["job_id"]
    assert os.path.isdir(os.path.join(app_module.OUTPUT_FOLDER, job_id))
    # two XLSX should exist (for a.pdf, b.pdf). Our stub_writer creates exact basenames.
    assert os.path.isfile(os.path.join(app_module.OUTPUT_FOLDER, job_id, "a.xlsx"))
    assert os.path.isfile(os.path.join(app_module.OUTPUT_FOLDER, job_id, "b.xlsx"))
