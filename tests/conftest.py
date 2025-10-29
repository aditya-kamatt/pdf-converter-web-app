import io
import json
import os
import types
import builtins
#import pandas as pd
import pytest

import sys, pathlib 
ROOT = pathlib.Path(__file__).resolve().parents[1]          #Project repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture
def app_module(tmp_path, monkeypatch):
    import importlib
    import app as app_mod

    # Redirect upload/output dirs to tmp
    monkeypatch.setattr(app_mod, "UPLOAD_FOLDER", str(tmp_path / "uploads"), raising=False)
    monkeypatch.setattr(app_mod, "OUTPUT_FOLDER", str(tmp_path / "outputs"), raising=False)
    os.makedirs(app_mod.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(app_mod.OUTPUT_FOLDER, exist_ok=True)

    def fake_render_template(template_name, **ctx):
        return f"TEMPLATE:{template_name}|CTX:{json.dumps(ctx, default=str)}"
    monkeypatch.setattr(app_mod, "render_template", fake_render_template, raising=True)

    return app_mod

@pytest.fixture
def client(app_module):
    app = app_module.app
    app.config.update(TESTING=True)
    return app.test_client()

# Reusable in-memory "PDF" file
@pytest.fixture
def pdf_file():
    return io.BytesIO(b"%PDF-1.4\n%fake")  

@pytest.fixture
def happy_extract(monkeypatch):
    def fake_header_meta(pdf_path):
        return {"title": "Mock PDF", "source": pdf_path}
    def fake_table_rows(pdf_path):
        return [["col1", "col2"], ["a", "1"], ["b", "2"]]
    monkeypatch.setattr("app.extract_header_meta", fake_header_meta)
    monkeypatch.setattr("app.extract_table_rows", fake_table_rows)

@pytest.fixture
def failing_extract(monkeypatch):
    def boom(pdf_path):
        raise RuntimeError("boom")
    monkeypatch.setattr("app.extract_header_meta", lambda p: {"k": "v"})
    monkeypatch.setattr("app.extract_table_rows", boom)

@pytest.fixture
def stub_writer(monkeypatch):
    def fake_write_to_excel(df, meta, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"XLSX")
    monkeypatch.setattr("app.write_to_excel", fake_write_to_excel)
