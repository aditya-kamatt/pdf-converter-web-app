import pytest

def pytest_addoption(parser):
    parser.addoption("--update-golden", action="store_true", help="Update expected XLSX files")

@pytest.fixture
def update_golden(request) -> bool:
    return bool(request.config.getoption("--update-golden"))




