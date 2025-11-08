import pytest

def pytest_addoption(parser):
    parser.addoption(
        "--update-golden", 
        action="store_true", 
        default=False,
        help="Update expected XLSX files"
    )

@pytest.fixture
def update_golden(request) -> bool:
    return bool(request.config.getoption("--update-golden", default=False))




