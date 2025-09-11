from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template,
    flash,
    redirect,
    url_for,
)
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime
import pandas as pd

# Import your existing modules
from core.parser import extract_header_meta, extract_table_rows
from excel_io.excel_writer import write_to_excel
from pdf_utils.logging_config import setup_logging

# -----------------------------------------------------------------------------
# App & logging setup
# -----------------------------------------------------------------------------
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "your-secret-key-change-this"  # Change this in production
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max upload

ALLOWED_EXTENSIONS = {"pdf"}
UPLOAD_FOLDER = "temp_uploads"
OUTPUT_FOLDER = "temp_outputs"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def allowed_file(filename: str) -> bool:
    """Return True if the file extension is allowed (PDF)."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_data_from_pdf(pdf_path: str):
    """Extract metadata and tabular data from a PDF and return (meta, DataFrame)."""
    try:
        meta = extract_header_meta(pdf_path)
        logger.info(f"Extracted metadata: {meta}")

        rows = extract_table_rows(pdf_path)
        if not rows or len(rows) <= 1:
            raise ValueError("No data rows found in PDF")

        header = rows[0]
        data_rows = rows[1:]
        df = pd.DataFrame(data_rows, columns=header)
        logger.info(
            f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns"
        )
        return meta, df
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {e}")
        raise


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@app.route("/")
def index():
    """Main upload page."""
    # You can pass defaults to the template if you want to pre-select an option
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert_pdf():
    """Handle PDF conversion via web form."""
    try:
        if "file" not in request.files:
            flash("No file selected", "error")
            return redirect(url_for("index"))

        file = request.files["file"]
        if file.filename == "":
            flash("No file selected", "error")
            return redirect(url_for("index"))

        if not allowed_file(file.filename):
            flash("Please upload a PDF file", "error")
            return redirect(url_for("index"))

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        logger.info(f"Saved uploaded file to: {pdf_path}")

        meta, df = extract_data_from_pdf(pdf_path)

        # Include the layout in the output filename for clarity
        base = filename.rsplit(".", 1)[0]
        excel_filename = f"{timestamp}_converted_{base}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)

        # Pass the layout through to the writer
        write_to_excel(df, meta, excel_path)
        logger.info(f"Created Excel file: {excel_path}")

        # Best-effort cleanup of uploaded PDF
        try:
            os.remove(pdf_path)
        except OSError:
            logger.warning(f"Could not remove uploaded file: {pdf_path}")

        return send_file(
            excel_path,
            as_attachment=True,
            download_name=excel_filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.error(f"Error during conversion: {e}")
        flash(f"Error processing file: {e}", "error")
        return redirect(url_for("index"))


@app.route("/api/convert", methods=["POST"])
def api_convert():
    """API endpoint for programmatic PDF -> Excel conversion."""
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No file selected"}), 400

        if not allowed_file(file.filename):
            return jsonify({"error": "Only PDF files are allowed"}), 400

        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)

        meta, df = extract_data_from_pdf(pdf_path)

        base = filename.rsplit(".", 1)[0]
        excel_filename = f"{timestamp}_converted_{base}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)

        write_to_excel(df, meta, excel_path)

        # Best-effort cleanup
        try:
            os.remove(pdf_path)
        except OSError:
            pass

        return jsonify(
            {
                "success": True,
                "message": "File converted successfully",
                "metadata": meta,
                "rows_processed": int(df.shape[0]),
                "download_url": f"/download/{excel_filename}",
            }
        )
    except Exception as e:
        logger.error(f"API conversion error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/download/<filename>")
def download_file(filename):
    """Download converted Excel files."""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return jsonify({"error": "Error downloading file"}), 500


@app.route("/health")
def health_check():
    """Basic health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.1.0",  # bumped due to layout switch feature
        }
    )


@app.errorhandler(413)
def too_large(e):
    flash("File too large. Maximum size is 16MB.", "error")
    return redirect(url_for("index"))


@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    flash("An unexpected error occurred. Please try again.", "error")
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Maintenance helper
# -----------------------------------------------------------------------------


def cleanup_old_files(hours: int = 1):
    """Remove files in upload/output folders older than `hours`."""
    import time

    cutoff = time.time() - hours * 3600
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            if os.path.isfile(fpath) and os.path.getctime(fpath) < cutoff:
                try:
                    os.remove(fpath)
                    logger.info(f"Cleaned up old file: {fpath}")
                except OSError:
                    logger.warning(f"Could not remove old file: {fpath}")


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # For local development. Consider using an env var for PORT when deploying.
    app.run(debug=True, host="0.0.0.0", port=5000)
