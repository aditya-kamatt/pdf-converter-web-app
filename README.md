# PDF Converter Web App

Lightweight Flask application for converting PDFs into structured data and files (e.g., text and spreadsheets), with simple upload → process → download flows and temporary storage for inputs/outputs.

## Features

- Upload single or multiple PDF files.
- Convert pages to extracted **text**.
- Export detected tabular data to **Excel/CSV**.
- Basic PDF utilities (e.g., page selection, simple merges/splits if enabled).
- Ephemeral storage using `temp_uploads/` and `temp_outputs/`.
- Minimal HTML templates for a clean web UI.

> NOTE: Exact feature coverage depends on the utilities enabled in `core/`, `pdf_utils/`, and `excel_io/`. See code comments for specifics.

## Tech Stack

- **Backend:** Python, Flask  
- **PDF Processing:** `pdfplumber`  
- **Data:** `pandas`, `openpyxl` (for Excel/CSV)  
- **Frontend:** Jinja2 templates (in `templates/`)  
- **Deploy:** Procfile included (compatible with Heroku/Render)

## Project Structure

```plaintext
pdf-converter-web-app/
├─ app.py                 # Flask entrypoint 
├─ core/                  # Shared helpers/config, request handling
├─ pdf_utils/             # PDF parsing/conversion utilities
├─ excel_io/              # Table extraction & Excel/CSV writer
├─ templates/             # HTML template
├─ temp_uploads/          # Ephemeral uploads (gitignored)
├─ temp_outputs/          # Generated files (gitignored)
├─ requirements.txt       # Python dependencies
├─ Procfile               # Web process declaration for deployment
├─ .pre-commit-config.yaml
└─ .gitignore
```

## Usage

### Prerequisites
- Python 3.10+ recommended
- Linux/macOS/WSL (works on Windows too)
- (Linux) System deps may be required for PDF libraries.

### Setup
Follow these steps to set up the project locally.

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
#### 4. Run the app
```bash
flask --app app.py run

flask run
```
By default, the app runs at: [http://127.0.0.1:5000](http://127.0.0.1:5000)
#### 5. (Optional) Development Mode
Enable auto-reload and debug mode:
```bash
export FLASK_ENV=development  # Linux/macOS
set FLASK_ENV=development     # Windows (Command Prompt)
$env:FLASK_ENV="development"  # Windows (PowerShell)
```
