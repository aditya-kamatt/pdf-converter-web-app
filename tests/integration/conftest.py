"""
Fixtures for integration tests.
"""
import pytest
import pathlib
import sys

# Add project root to path
HERE = pathlib.Path(__file__).parent
PROJECT_ROOT = HERE.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def real_pdf_fixture():
    """
    Provides a real PDF file from the golden test inputs.
    Returns (path, filename) tuple.
    """
    golden_inputs = PROJECT_ROOT / "tests" / "golden" / "inputs"
    pdf_files = list(golden_inputs.glob("*.pdf"))
    
    if not pdf_files:
        pytest.skip("No PDF files found in golden/inputs")
    
    # Use the first PDF file
    pdf_path = pdf_files[0]
    return str(pdf_path), pdf_path.name


@pytest.fixture
def multiple_real_pdfs():
    """
    Provides multiple real PDF files from golden test inputs.
    Returns list of (path, filename) tuples.
    """
    golden_inputs = PROJECT_ROOT / "tests" / "golden" / "inputs"
    pdf_files = list(golden_inputs.glob("*.pdf"))
    
    if not pdf_files:
        pytest.skip("No PDF files found in golden/inputs")
    
    return [(str(p), p.name) for p in pdf_files[:3]]  # Return up to 3 PDFs

