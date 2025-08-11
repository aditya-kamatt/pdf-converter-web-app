from flask import Flask, request, jsonify, send_file, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import tempfile
import os
import logging
from datetime import datetime
import pandas as pd

# Import your existing modules with corrected paths
from core.parser import extract_header_meta, extract_table_rows
from excel_io.excel_writer import write_to_excel
from pdf_utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = 'temp_uploads'
OUTPUT_FOLDER = 'temp_outputs'

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the uploaded file is a PDF."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_data_from_pdf(pdf_path):
    """
    Extract data from PDF using your existing parser logic.
    Returns meta and DataFrame.
    """
    try:
        # Extract metadata
        meta = extract_header_meta(pdf_path)
        logger.info(f"Extracted metadata: {meta}")
        
        # Extract table rows
        rows = extract_table_rows(pdf_path)
        
        if not rows or len(rows) <= 1:
            raise ValueError("No data rows found in PDF")
        
        # Convert to DataFrame
        header = rows[0]
        data_rows = rows[1:]
        df = pd.DataFrame(data_rows, columns=header)
        
        logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        return meta, df
        
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {str(e)}")
        raise

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_pdf():
    """Handle PDF conversion."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_file(file.filename):
            flash('Please upload a PDF file', 'error')
            return redirect(url_for('index'))
        
        # Secure the filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save uploaded file
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        logger.info(f"Saved uploaded file to: {pdf_path}")
        
        # Extract data from PDF
        meta, df = extract_data_from_pdf(pdf_path)
        
        # Create output Excel file
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        # Write to Excel using your existing function
        write_to_excel(df, meta, excel_path)
        
        logger.info(f"Created Excel file: {excel_path}")
        
        # Clean up uploaded PDF
        try:
            os.remove(pdf_path)
        except OSError:
            logger.warning(f"Could not remove uploaded file: {pdf_path}")
        
        # Return the Excel file
        return send_file(
            excel_path,
            as_attachment=True,
            download_name=f"converted_{filename.rsplit('.', 1)[0]}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API endpoint for programmatic access."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Process file similar to web interface
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        # Extract and convert
        meta, df = extract_data_from_pdf(pdf_path)
        
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        write_to_excel(df, meta, excel_path)
        
        # Clean up
        try:
            os.remove(pdf_path)
        except OSError:
            pass
        
        # Return success response with metadata
        return jsonify({
            'success': True,
            'message': 'File converted successfully',
            'metadata': meta,
            'rows_processed': len(df),
            'download_url': f'/download/{excel_filename}'
        })
        
    except Exception as e:
        logger.error(f"API conversion error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download converted files."""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Error downloading file'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum size is 16MB.', 'error')
    return redirect(url_for('index'))

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}")
    flash('An unexpected error occurred. Please try again.', 'error')
    return redirect(url_for('index'))

# Cleanup old files periodically (you might want to run this as a background task)
def cleanup_old_files():
    """Remove files older than 1 hour."""
    import time
    current_time = time.time()
    
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path):
                file_age = current_time - os.path.getctime(file_path)
                if file_age > 3600:  # 1 hour
                    try:
                        os.remove(file_path)
                        logger.info(f"Cleaned up old file: {file_path}")
                    except OSError:
                        logger.warning(f"Could not remove old file: {file_path}")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)rom flask import Flask, request, jsonify, send_file, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# Import your existing modules
from core.parser import extract_header_meta, extract_table_rows
from pdf_utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = 'temp_uploads'
OUTPUT_FOLDER = 'temp_outputs'

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the uploaded file is a PDF."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_excel_from_rows(rows, meta, output_path):
    """Create Excel file without pandas dependency."""
    wb = Workbook()
    
    # Create Summary sheet
    summary_ws = wb.active
    summary_ws.title = "Summary"
    
    # Add summary data
    summary_data = [
        ['Field', 'Value'],
        ['PO Number', meta.get('po_number', 'N/A')],
        ['Vendor Number', meta.get('vendor_number', 'N/A')],
        ['Ship By Date', meta.get('ship_by_date', 'N/A')],
        ['Payment Terms', meta.get('payment_terms', 'N/A')],
        ['Total Amount', f"${meta.get('total', 'N/A')}" if meta.get('total') != 'N/A' else 'N/A'],
        ['Page Count', str(meta.get('page_count', 'N/A'))],
        ['Processing Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]
    
    for row in summary_data:
        summary_ws.append(row)
    
    # Format summary sheet
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for cell in summary_ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    # Adjust column widths
    summary_ws.column_dimensions['A'].width = 20
    summary_ws.column_dimensions['B'].width = 30
    
    # Create Orders sheet
    orders_ws = wb.create_sheet(title="Orders")
    
    # Add data rows
    for row in rows:
        orders_ws.append(row)
    
    # Format orders sheet header
    if rows:
        for cell in orders_ws[1]:
            cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal='center')
    
    # Auto-adjust column widths
    for column in orders_ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        
        # Set specific widths based on column content
        if column_letter == 'A':  # Qty
            adjusted_width = max(max_length + 2, 8)
        elif column_letter in ['B', 'C']:  # Item SKU, Dev Code
            adjusted_width = max(max_length + 2, 15)
        elif column_letter in ['D', 'E']:  # UPC, HTS Code
            adjusted_width = max(max_length + 2, 18)
        elif column_letter == 'F':  # Brand
            adjusted_width = max(max_length + 2, 15)
        elif column_letter == 'G':  # Description
            adjusted_width = min(max(max_length + 2, 20), 50)  # Cap at 50
        elif column_letter in ['H', 'I']:  # Rate, Amount
            adjusted_width = max(max_length + 2, 12)
        else:
            adjusted_width = max_length + 2
            
        orders_ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save the workbook
    wb.save(output_path)
    logger.info(f"Excel file created: {output_path}")

def extract_data_from_pdf(pdf_path):
    """Extract data from PDF using existing parser."""
    try:
        # Extract metadata
        meta = extract_header_meta(pdf_path)
        logger.info(f"Extracted metadata: {meta}")
        
        # Extract table rows
        rows = extract_table_rows(pdf_path)
        
        if not rows or len(rows) <= 1:
            raise ValueError("No data rows found in PDF")
        
        logger.info(f"Extracted {len(rows)} rows from PDF")
        return meta, rows
        
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {str(e)}")
        raise

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_pdf():
    """Handle PDF conversion."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_file(file.filename):
            flash('Please upload a PDF file', 'error')
            return redirect(url_for('index'))
        
        # Secure the filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save uploaded file
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        logger.info(f"Saved uploaded file to: {pdf_path}")
        
        # Extract data from PDF
        meta, rows = extract_data_from_pdf(pdf_path)
        
        # Create output Excel file
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        # Create Excel file
        create_excel_from_rows(rows, meta, excel_path)
        
        logger.info(f"Created Excel file: {excel_path}")
        
        # Clean up uploaded PDF
        try:
            os.remove(pdf_path)
        except OSError:
            logger.warning(f"Could not remove uploaded file: {pdf_path}")
        
        # Return the Excel file
        return send_file(
            excel_path,
            as_attachment=True,
            download_name=f"converted_{filename.rsplit('.', 1)[0]}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API endpoint for programmatic access."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Process file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        # Extract and convert
        meta, rows = extract_data_from_pdf(pdf_path)
        
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        create_excel_from_rows(rows, meta, excel_path)
        
        # Clean up
        try:
            os.remove(pdf_path)
        except OSError:
            pass
        
        # Return success response
        return jsonify({
            'success': True,
            'message': 'File converted successfully',
            'metadata': meta,
            'rows_processed': len(rows) - 1,  # Subtract header row
            'download_url': f'/download/{excel_filename}'
        })
        
    except Exception as e:
        logger.error(f"API conversion error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download converted files."""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Error downloading file'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)rom flask import Flask, request, jsonify, send_file, render_template, flash, redirect, url_for
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

# Import your existing modules
from core.parser import extract_header_meta, extract_table_rows
from pdf_utils.logging_config import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

ALLOWED_EXTENSIONS = {'pdf'}
UPLOAD_FOLDER = 'temp_uploads'
OUTPUT_FOLDER = 'temp_outputs'

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if the uploaded file is a PDF."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_excel_from_rows(rows, meta, output_path):
    """Create Excel file without pandas dependency."""
    wb = Workbook()
    
    # Create Summary sheet
    summary_ws = wb.active
    summary_ws.title = "Summary"
    
    # Add summary data
    summary_data = [
        ['Field', 'Value'],
        ['PO Number', meta.get('po_number', 'N/A')],
        ['Vendor Number', meta.get('vendor_number', 'N/A')],
        ['Ship By Date', meta.get('ship_by_date', 'N/A')],
        ['Payment Terms', meta.get('payment_terms', 'N/A')],
        ['Total Amount', f"${meta.get('total', 'N/A')}" if meta.get('total') != 'N/A' else 'N/A'],
        ['Page Count', str(meta.get('page_count', 'N/A'))],
        ['Processing Date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
    ]
    
    for row in summary_data:
        summary_ws.append(row)
    
    # Format summary sheet
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    
    for cell in summary_ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center')
    
    # Adjust column widths
    summary_ws.column_dimensions['A'].width = 20
    summary_ws.column_dimensions['B'].width = 30
    
    # Create Orders sheet
    orders_ws = wb.create_sheet(title="Orders")
    
    # Add data rows
    for row in rows:
        orders_ws.append(row)
    
    # Format orders sheet header
    if rows:
        for cell in orders_ws[1]:
            cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(horizontal='center')
    
    # Auto-adjust column widths
    for column in orders_ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        
        # Set specific widths based on column content
        if column_letter == 'A':  # Qty
            adjusted_width = max(max_length + 2, 8)
        elif column_letter in ['B', 'C']:  # Item SKU, Dev Code
            adjusted_width = max(max_length + 2, 15)
        elif column_letter in ['D', 'E']:  # UPC, HTS Code
            adjusted_width = max(max_length + 2, 18)
        elif column_letter == 'F':  # Brand
            adjusted_width = max(max_length + 2, 15)
        elif column_letter == 'G':  # Description
            adjusted_width = min(max(max_length + 2, 20), 50)  # Cap at 50
        elif column_letter in ['H', 'I']:  # Rate, Amount
            adjusted_width = max(max_length + 2, 12)
        else:
            adjusted_width = max_length + 2
            
        orders_ws.column_dimensions[column_letter].width = adjusted_width
    
    # Save the workbook
    wb.save(output_path)
    logger.info(f"Excel file created: {output_path}")

def extract_data_from_pdf(pdf_path):
    """Extract data from PDF using existing parser."""
    try:
        # Extract metadata
        meta = extract_header_meta(pdf_path)
        logger.info(f"Extracted metadata: {meta}")
        
        # Extract table rows
        rows = extract_table_rows(pdf_path)
        
        if not rows or len(rows) <= 1:
            raise ValueError("No data rows found in PDF")
        
        logger.info(f"Extracted {len(rows)} rows from PDF")
        return meta, rows
        
    except Exception as e:
        logger.error(f"Error extracting data from PDF: {str(e)}")
        raise

@app.route('/')
def index():
    """Main upload page."""
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_pdf():
    """Handle PDF conversion."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
        
        if not allowed_file(file.filename):
            flash('Please upload a PDF file', 'error')
            return redirect(url_for('index'))
        
        # Secure the filename
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save uploaded file
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        logger.info(f"Saved uploaded file to: {pdf_path}")
        
        # Extract data from PDF
        meta, rows = extract_data_from_pdf(pdf_path)
        
        # Create output Excel file
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        # Create Excel file
        create_excel_from_rows(rows, meta, excel_path)
        
        logger.info(f"Created Excel file: {excel_path}")
        
        # Clean up uploaded PDF
        try:
            os.remove(pdf_path)
        except OSError:
            logger.warning(f"Could not remove uploaded file: {pdf_path}")
        
        # Return the Excel file
        return send_file(
            excel_path,
            as_attachment=True,
            download_name=f"converted_{filename.rsplit('.', 1)[0]}.xlsx",
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
    except Exception as e:
        logger.error(f"Error during conversion: {str(e)}")
        flash(f'Error processing file: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/api/convert', methods=['POST'])
def api_convert():
    """API endpoint for programmatic access."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Only PDF files are allowed'}), 400
        
        # Process file
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        pdf_path = os.path.join(UPLOAD_FOLDER, f"{timestamp}_{filename}")
        file.save(pdf_path)
        
        # Extract and convert
        meta, rows = extract_data_from_pdf(pdf_path)
        
        excel_filename = f"{timestamp}_converted_{filename.rsplit('.', 1)[0]}.xlsx"
        excel_path = os.path.join(OUTPUT_FOLDER, excel_filename)
        
        create_excel_from_rows(rows, meta, excel_path)
        
        # Clean up
        try:
            os.remove(pdf_path)
        except OSError:
            pass
        
        # Return success response
        return jsonify({
            'success': True,
            'message': 'File converted successfully',
            'metadata': meta,
            'rows_processed': len(rows) - 1,  # Subtract header row
            'download_url': f'/download/{excel_filename}'
        })
        
    except Exception as e:
        logger.error(f"API conversion error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Download converted files."""
    try:
        file_path = os.path.join(OUTPUT_FOLDER, filename)
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return jsonify({'error': 'Error downloading file'}), 500

@app.route('/health')
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
