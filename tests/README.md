# Test Suite Documentation

## Quick Start

### Run all tests
```bash
pytest --all
```

### Run specific test suites
```bash
# Unit tests only
pytest tests/core/ tests/excel_io/

# Integration tests
pytest tests/integration/

# Golden tests
pytest tests/golden/

# Quick smoke test (fast tests only)
pytest -k "not slow"
```

### Run with coverage
```bash
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=term-missing
```

---

## Test Organization

```
tests/
├── conftest.py              # Global fixtures and test configuration
├── core/                    # Unit tests for core modules
│   ├── test_app.py          # Flask app tests
│   ├── test_app_errors.py   # Error handling tests
│   ├── test_parser.py       # PDF parser tests
│   ├── test_parser_helpers.py    # Parser helper function tests
│   ├── test_parser_error_recovery.py  # Parser fallback tests
│   └── test_validator.py    # Data validation tests
├── excel_io/                # Excel writer tests
│   ├── test_excel_writer.py      # Basic writer tests
│   └── test_excel_formatting.py  # Formatting verification tests
├── integration/             # End-to-end integration tests
│   ├── conftest.py          # Integration test fixtures
│   └── test_e2e_workflows.py     # Full workflow tests
└── golden/                  # Golden/snapshot tests
    ├── conftest.py          # Golden test fixtures
    ├── inputs/              # Sample PDF files
    ├── expected/            # Expected Excel outputs
    └── test_golden_excel.py # Golden comparison tests
```

---

## Test Categories

### Unit Tests (`tests/core/`, `tests/excel_io/`)
Fast, isolated tests for individual functions and classes.

**When to run:** Always, on every commit

```bash
pytest tests/core/ tests/excel_io/ -v
```

### Integration Tests (`tests/integration/`)
End-to-end tests using real PDFs and verifying complete workflows.

**When to run:** Before merging, as part of CI/CD

```bash
pytest tests/integration/ -v
```

**What they test:**
- Complete upload → process → download workflows
- API endpoints with real data
- File system state management
- Concurrent request handling
- Error scenarios with invalid files

### Golden Tests (`tests/golden/`)
Snapshot tests comparing PDF→Excel conversions against known-good outputs.

**When to run:** Before releases, when changing extraction logic

```bash
pytest tests/golden/ -v
```

**Update golden files:**
```bash
pytest tests/golden/ --update-golden
```

---

## Custom Flags

### `--all`
Run all tests in the suite (unit, integration, golden, formatting).

```bash
pytest --all
```

### `--update-golden`
Update the expected Excel files in golden tests.

```bash
pytest tests/golden/ --update-golden
```

### Standard pytest flags
```bash
# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run specific test
pytest tests/core/test_parser.py::test_to_float_valid_numbers

# Run tests matching pattern
pytest -k "parser"

# Show slowest tests
pytest --durations=10
```

---

## Markers

Tests can be marked with categories:

- `@pytest.mark.golden` - Golden/snapshot tests
- `@pytest.mark.integration` - Integration tests (slower)
- `@pytest.mark.formatting` - Formatting verification tests
- `@pytest.mark.error_recovery` - Error recovery tests

### Run tests by marker
```bash
pytest -m golden
pytest -m integration
pytest -m "not integration"  # Skip integration tests
```

---

## Common Tasks

### Run fast tests only
```bash
pytest tests/core/ tests/excel_io/ -v
```

### Run full CI/CD test suite
```bash
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=term-missing
```

### Debug a failing test
```bash
pytest tests/integration/test_e2e_workflows.py::TestEndToEndWebWorkflow::test_complete_conversion_workflow_web -vvs --tb=long
```

### Check test collection (don't run)
```bash
pytest --collect-only
```

---

## Writing New Tests

### Test file naming
- `test_*.py` - Test files must start with `test_`
- `*_test.py` - Alternative naming (not used in this project)

### Test function naming
```python
def test_something_specific():
    """Test that something specific works correctly."""
    # Arrange
    input_data = create_test_data()
    
    # Act
    result = function_under_test(input_data)
    
    # Assert
    assert result == expected_value
```

### Use fixtures
```python
def test_with_fixture(client, app_module):
    """Test using shared fixtures."""
    response = client.get("/health")
    assert response.status_code == 200
```

### Parametrize tests
```python
@pytest.mark.parametrize("input,expected", [
    (10, 20),
    (5, 10),
    (0, 0),
])
def test_doubles_number(input, expected):
    assert double(input) == expected
```

---

## Coverage

### Generate coverage report
```bash
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=html
```

Then open `htmlcov/index.html` in a browser.

### View coverage in terminal
```bash
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=term-missing
```

---

## CI/CD Integration

The test suite runs automatically on:
- Every pull request
- Every push to main
- Python versions: 3.10, 3.11, 3.12, 3.13

See `.github/workflows/ci.yml` for configuration.

---

## Troubleshooting

### Tests fail with import errors
**Solution:** Install dependencies
```bash
pip install -r requirements.txt
pip install pytest pytest-cov
```

### Integration tests fail with "No PDFs found"
**Solution:** Ensure golden test PDFs exist
```bash
ls tests/golden/inputs/*.pdf
```

### Permission errors on temp files
**Solution:** Tests use `tmp_path` fixture which handles cleanup automatically. If issues persist:
```bash
rm -rf /tmp/pytest-of-*
```

### Tests are too slow
**Solution:** Run only fast tests
```bash
pytest tests/core/ tests/excel_io/ -v
```

Or use pytest-xdist for parallel execution:
```bash
pip install pytest-xdist
pytest -n auto
```

---

## Test Statistics

- **Total tests:** ~100+ tests
- **Unit tests:** ~70 tests (~10 seconds)
- **Integration tests:** 12 tests (~60 seconds)
- **Golden tests:** 10 tests (~30 seconds)
- **Formatting tests:** 20 tests (~5 seconds)

---

## Need Help?

- Check test output for detailed error messages
- Run with `-vvs --tb=long` for maximum verbosity
- Check `pytest.ini` for configuration
- See `.github/workflows/ci.yml` for CI setup

