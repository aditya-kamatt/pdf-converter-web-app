# PDF Converter Web App

![CI/CD](https://github.com/aditya-kamatt/pdf-converter-web-app/workflows/CI%20-%20Test%20%26%20Lint/badge.svg)
[![codecov](https://codecov.io/gh/aditya-kamatt/pdf-converter-web-app/branch/main/graph/badge.svg)](https://codecov.io/gh/aditya-kamatt/pdf-converter-web-app)

Lightweight Flask application for converting vendor purchase order PDFs into structured Excel spreadsheets, with automated testing, CI/CD pipeline, and production deployment on Railway.

## Features

- **PDF Upload & Conversion**: Upload purchase order PDFs and convert to structured Excel files
- **Multi-Sheet Excel Output**: 
  - Summary sheet with PO metadata (PO number, vendor, ship date, payment terms, total)
  - Orders sheet with line-item details
  - SizeSheet with product size breakdowns
- **Intelligent Data Extraction**: Three-tier extraction strategy (position-based → table-based → regex fallback)
- **Data Validation**: UPC check digit validation, arithmetic checks, QA reporting
- **Web Interface**: Clean, modern UI with drag-and-drop file upload
- **REST API**: Programmatic access via `/api/convert` endpoint
- **Automated CI/CD**: Tests run on every PR, automatic deployment on merge
- **Production Ready**: Deployed on Railway with health monitoring

## Tech Stack

- **Backend:** Python 3.13, Flask
- **PDF Processing:** `pdfplumber`, `PyPDF2`, `pdfminer.six`
- **Data Processing:** `pandas`, `numpy`
- **Excel Generation:** `openpyxl`
- **Frontend:** Jinja2 templates with modern CSS
- **Testing:** `pytest`, `pytest-cov`, coverage tracking via Codecov
- **CI/CD:** GitHub Actions, automatic Railway deployment
- **Deployment:** Railway (production), Gunicorn (WSGI server)

## Project Structure

```plaintext
pdf-converter-web-app/
├── app.py                      # Flask application entrypoint
├── core/
│   ├── parser.py              # PDF extraction logic (position/table/regex)
│   ├── validator.py           # Data validation and QA checks
│   └── logging_config.py      # Logging configuration
├── excel_io/
│   └── excel_writer.py        # Excel file generation with formatting
├── templates/
│   └── index.html             # Web UI template
├── tests/
│   ├── core/                  # Unit tests for core modules
│   │   ├── test_app.py
│   │   ├── test_app_errors.py
│   │   ├── test_parser.py
│   │   ├── test_parser_helpers.py
│   │   └── test_validator.py
│   ├── excel_io/              # Excel writer tests
│   │   └── test_excel_writer.py
│   └── golden/                # End-to-end golden tests
│       ├── inputs/            # Sample PDFs
│       ├── expected/          # Expected Excel outputs
│       └── test_golden_excel.py
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions CI/CD pipeline
├── requirements.txt           # Python dependencies
├── Procfile                   # Railway/Heroku deployment config
├── pytest.ini                 # Pytest configuration
├── .flake8                    # Code linting rules
└── .gitignore                 # Git ignore rules
```

## Quick Start

### Prerequisites

- Python 3.11+ (tested on 3.13)
- Git
- Virtual environment tool
- (Linux) `libmagickwand-dev` for ImageMagick support

### Local Development Setup

#### 1. Clone the repository

```bash
git clone https://github.com/aditya-kamatt/pdf-converter-web-app.git
cd pdf-converter-web-app
```

#### 2. Create and activate virtual environment

```bash
python -m venv .venv

# On Linux/macOS
source .venv/bin/activate

# On Windows (PowerShell)
.venv\Scripts\Activate
```

#### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Run the application

```bash
# Development mode
flask --app app.py run --debug

# Or simply
python app.py
```

The app will be available at [http://127.0.0.1:5000](http://127.0.0.1:5000)

#### 5. Access the web interface

1. Open your browser to `http://localhost:5000`
2. Upload a purchase order PDF
3. Click "Convert to Excel"
4. Download the generated Excel file

## API Usage

### Convert PDF via API

```bash
curl -X POST http://localhost:5000/api/convert \
  -F "file=@/path/to/purchase_order.pdf" \
  -o output.xlsx
```

### Health Check

```bash
curl http://localhost:5000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-08T19:00:00",
  "version": "1.1.0"
}
```

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=core --cov=excel_io --cov=app --cov-report=html

# Run specific test file
pytest tests/core/test_validator.py -v

# Run tests matching pattern
pytest tests/ -k "validator" -v
```

### Test Coverage

- Error handling (invalid files, missing data, API errors)
- Data validation (UPC check digits, arithmetic checks)
- Edge cases (NaN values, Unicode, special characters)
- Helper functions (parsing, formatting, validation)
- End-to-end conversion (10 golden test PDFs)

### Golden Tests

Golden tests validate end-to-end PDF → Excel conversion:

```bash
# Run golden tests only
pytest tests/golden/ -v

# Update golden files (after verifying changes)
pytest tests/golden/ --update-golden
```

## CI/CD Pipeline

### Automated Testing

On every pull request to `main`:

1. **Environment Setup**: Python 3.13, system dependencies
2. **Code Quality**: Flake8 linting, Black formatting check
3. **Test Execution**: Full test suite with coverage
4. **Coverage Report**: Results uploaded to Codecov
5. **PR Comment**: Automated status comment on pull request

### Branch Protection

The `main` branch is protected:
- ✅ Pull requests required
- ✅ Tests must pass before merge
- ✅ Conversations must be resolved
- ✅ Branch must be up to date

### Deployment

**Production:** Deployed on Railway
- **Auto-deploy:** Merging to `main` triggers automatic deployment
- **Health Check:** `/health` endpoint monitored

**Workflow:**
```
dev branch → Create PR → Tests run → Tests pass → 
Merge to main → Railway deploys → App live
```

## Code Quality

### Linting

```bash
# Check code quality
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics

# Format code
black .
```

### Pre-commit Hooks (Optional)

```bash
pip install pre-commit
pre-commit install
```

## Data Flow

```
┌─────────────┐
│   PDF File  │
└──────┬──────┘
       │
       ↓
┌─────────────────────────────┐
│  Position-Based Extraction  │ ← Primary method
│  (Word geometry analysis)   │
└──────┬──────────────────────┘
       │ (if fails)
       ↓
┌─────────────────────────────┐
│   Table-Based Extraction    │ ← Secondary method
│  (pdfplumber tables)        │
└──────┬──────────────────────┘
       │ (if fails)
       ↓
┌─────────────────────────────┐
│    Regex Fallback           │ ← Last resort
│  (Pattern matching)         │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│   Data Validation           │
│  • UPC check digits         │
│  • Arithmetic validation    │
│  • Missing data checks      │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────────────────────┐
│   Excel Generation          │
│  • Summary Sheet            │
│  • Orders Sheet             │
│  • SizeSheet                │
└──────┬──────────────────────┘
       │
       ↓
┌─────────────┐
│ Excel File  │
└─────────────┘
```

## Configuration

### Environment Variables

None required for basic operation. Optional:

- `SECRET_KEY`: Flask secret key for session management (uses default in development)
- `FLASK_ENV`: Set to `development` for debug mode
- `PORT`: Server port (default: 5000)

### Application Settings

In `app.py`:

```python
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload
ALLOWED_EXTENSIONS = {"pdf"}

# Automatic cleanup of temporary files older than 24 hours on startup
cleanup_old_files(hours=24)
```

## Error Handling

The application includes comprehensive error handling:

- **Invalid file types**: Returns 400 with error message
- **Missing files**: Returns 400 with error message
- **Parsing errors**: Returns 500 with error details
- **File too large (>16MB)**: Returns 413 error
- **Missing data in PDF**: Returns error with specifics

## Results: Skills & Technologies Learned

Through developing this application, I have gained experience with a diverse set of modern software engineering tools, libraries, and concepts, including:

### Backend & Core Skills
- **Python 3.13**: Advanced Python programming, including type annotation, exception handling, and file system operations.
- **Flask**: Creating robust RESTful APIs, request handling, secure file uploads, and configuration management.
- **PDF Processing**: Harnessing multiple libraries (`pdfplumber`, `PyPDF2`, `pdfminer.six`) for complex PDF extraction workflows, including table and regex-based parsing.
- **Data Processing with pandas & numpy**: Cleaning, validating, and transforming tabular data efficiently, including use of DataFrames, type coercion, and advanced string operations.
- **Custom Validation Logic**: Implementing domain-specific rules such as UPC check digit verification, arithmetic consistency checks, and missing data detection.

### Frontend & Presentation
- **Jinja2 Templates**: Designing clean web interfaces with powerful templating and integration of modern CSS.
- **User Experience**: Building user-centric workflows for seamless upload, feedback, error notification, and download.

### Excel Automation
- **openpyxl**: Automated generation of multi-sheet, formatted Excel files, including summary and detail tabs.

### Testing & Quality Assurance
- **pytest & pytest-cov**: Writing robust, maintainable unit and end-to-end tests.
- **Golden Master Testing**: Building golden input/output test infrastructure to ensure regressions are caught across real-world sample PDFs.
- **CI/CD Automation**: Leveraging GitHub Actions for automated testing and deployment.

### DevOps & Best Practices
- **Virtual Environments**: Managing dependencies and isolated development using Python venv.
- **Git**: Effective use of version control for collaboration, branching, and code review.
- **Deployment**: Automated cloud deployments using Railway, process management via Gunicorn, and environment configuration.
- **Code Linting & Quality**: Enforcing formatting and quality standards with `.flake8`.

### Soft Skills Developed
- **Debugging & Error Handling**: Diagnosing complex parsing and production issues.
- **Documentation**: Authoring clear README and code comments for future maintainers.
- **Workflow Integration**: Coordinating between backend logic, frontend UI, and external stakeholders’ needs.

This project provided hands-on experience with each stage of a cloud-native data-processing web tool, from low-level PDF extraction to cloud deployment and automated validation pipelines—a full-stack, production-grade learning journey.



