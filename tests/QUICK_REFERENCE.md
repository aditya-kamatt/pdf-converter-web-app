# Testing Quick Reference

## Most Common Commands

```bash
# Run all tests
pytest --all

# Run fast tests only (unit tests)
pytest tests/core/ tests/excel_io/

# Run with coverage
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=term-missing

# Debug a specific test
pytest tests/integration/test_e2e_workflows.py::test_name -vvs

# Update golden test expectations
pytest tests/golden/ --update-golden
```

---

## Test Suites

| Command | What it runs | Duration |
|---------|--------------|----------|
| `pytest --all` | Everything | ~100s |
| `pytest tests/core/ tests/excel_io/` | Unit tests | ~10s |
| `pytest tests/integration/` | Integration tests | ~60s |
| `pytest tests/golden/` | Golden tests | ~30s |

---

## Useful Flags

| Flag | Purpose |
|------|---------|
| `--all` | Run all tests |
| `-v` | Verbose output |
| `-vv` | Extra verbose |
| `-s` | Show print statements |
| `-x` | Stop on first failure |
| `-k "pattern"` | Run tests matching pattern |
| `--tb=short` | Short traceback |
| `--tb=long` | Full traceback |
| `--lf` | Run last failed tests |
| `--ff` | Run failures first |
| `--durations=10` | Show 10 slowest tests |
| `--collect-only` | List tests without running |

---

## Test Markers

```bash
# Run by marker
pytest -m golden           # Only golden tests
pytest -m integration      # Only integration tests
pytest -m "not integration"  # Skip integration tests
```

---

## Coverage

```bash
# Terminal report with missing lines
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=term-missing

# HTML report (open htmlcov/index.html)
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=html

# Both
pytest --all --cov=core --cov=excel_io --cov=app --cov-report=html --cov-report=term
```

---

## Debugging

```bash
# Maximum verbosity for debugging
pytest path/to/test.py::test_function -vvs --tb=long --log-cli-level=DEBUG

# Run with Python debugger
pytest --pdb

# Drop into debugger on failure
pytest --pdb -x
```

---

## Filtering Tests

```bash
# By path
pytest tests/core/test_parser.py

# By pattern
pytest -k "test_parser"
pytest -k "not slow"

# By marker
pytest -m integration

# Specific test
pytest tests/core/test_parser.py::TestClass::test_method
```

---

## CI/CD Commands

```bash
# What CI runs (full suite)
pytest tests/ -v \
  --cov=core \
  --cov=excel_io \
  --cov=app \
  --cov-report=xml \
  --cov-report=term-missing \
  --tb=short
```

---

## Installation

```bash
# Install test dependencies
pip install pytest pytest-cov

# Install project dependencies
pip install -r requirements.txt
```

---

## Common Issues

### Import errors
```bash
pip install -r requirements.txt
pip install pytest pytest-cov
```

### No PDFs found
```bash
ls tests/golden/inputs/*.pdf  # Should show PDF files
```

### Slow tests
```bash
# Run only fast tests
pytest tests/core/ tests/excel_io/

# Or use parallel execution
pip install pytest-xdist
pytest -n auto
```

---

## Examples

### Debug failing integration test
```bash
pytest tests/integration/test_e2e_workflows.py::TestEndToEndWebWorkflow::test_complete_conversion_workflow_web -vvs --tb=long
```

### Run all parser tests
```bash
pytest tests/core/test_parser*.py -v
```

### Check coverage for core module
```bash
pytest tests/core/ --cov=core --cov-report=term-missing
```

### Run only fast tests with coverage
```bash
pytest tests/core/ tests/excel_io/ --cov=core --cov=excel_io --cov-report=html
```

---

## Full Documentation

See `tests/README.md` for complete documentation.

