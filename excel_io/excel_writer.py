import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.styles import Alignment, Font, numbers, PatternFill, Border, Side
from openpyxl import load_workbook
import logging

def write_to_excel(df: pd.DataFrame, meta: dict, output_path: str):
    """
    Writes the DataFrame to an Excel file with a summary sheet and formatted data.
    
    Args:
        df: DataFrame containing the order data
        meta: Dictionary containing metadata about the order
        output_path: Path where the Excel file should be saved
    """
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # --- Summary Sheet ---
            create_summary_sheet(writer, meta)
            
            # --- Orders Sheet ---
            df.to_excel(writer, sheet_name='Orders', index=False)
            order_ws = writer.sheets['Orders']
            format_orders_sheet(order_ws, df)
            
        logging.info(f"Excel file written successfully to: {output_path}")
        
    except Exception as e:
        logging.error(f"Error writing Excel file: {str(e)}")
        raise

def create_summary_sheet(writer, meta: dict):
    """Create a summary sheet with order metadata."""
    # Create summary data
    summary_data = {
        'Field': [
            'PO Number',
            'Vendor Number', 
            'Ship By Date',
            'Payment Terms',
            'Total Amount',
            'Page Count',
            'Processing Date'
        ],
        'Value': [
            meta.get('po_number', 'N/A'),
            meta.get('vendor_number', 'N/A'),
            meta.get('ship_by_date', 'N/A'),
            meta.get('payment_terms', 'N/A'),
            f"${meta.get('total', 'N/A')}" if meta.get('total') != 'N/A' else 'N/A',
            str(meta.get('page_count', 'N/A')),
            pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        ]
    }
    
    summary_df = pd.DataFrame(summary_data)
    summary_df.to_excel(writer, sheet_name='Summary', index=False)
    
    # Format summary sheet
    summary_ws = writer.sheets['Summary']
    format_summary_sheet(summary_ws)

def format_summary_sheet(ws):
    """Apply formatting to the summary sheet."""
    # Header formatting
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=12)
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Data formatting
    data_font = Font(size=11)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = data_font
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 30
    
    # Add borders
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin_border

def format_orders_sheet(ws, df):
    """Apply formatting to the orders sheet."""
    # Header formatting
    header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Data formatting
    data_font = Font(size=10)
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = data_font
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # Adjust column widths based on content
    for col_idx, col in enumerate(df.columns, 1):
        column_letter = get_column_letter(col_idx)
        
        # Calculate max length for each column
        if len(df) > 0:
            max_len = max(
                df[col].astype(str).str.len().max() if not df[col].empty else 0,
                len(str(col))
            )
        else:
            max_len = len(str(col))
        
        # Set specific widths for known columns
        if col.lower() in ['description']:
            adjusted_width = min(max_len + 4, 50)  # Cap description at 50
        elif col.lower() in ['qty', 'rate', 'amount']:
            adjusted_width = max(max_len + 2, 12)
        elif col.lower() in ['item_sku', 'dev_code']:
            adjusted_width = max(max_len + 2, 15)
        elif col.lower() in ['upc', 'hts_code']:
            adjusted_width = max(max_len + 2, 18)
        else:
            adjusted_width = max_len + 2
        
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Format currency columns
    currency_format = '"$"#,##0.00'
    for col_idx, col in enumerate(df.columns, 1):
        if col.lower() in ['rate', 'amount']:
            column_letter = get_column_letter(col_idx)
            for row in range(2, len(df) + 2):
                ws[f'{column_letter}{row}'].number_format = currency_format
    
    # Add borders to all cells
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for row in ws.iter_rows():
        for cell in row:
            cell.border = thin_border
    
    # Alternate row colors for better readability
    light_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    for row_idx, row in enumerate(ws.iter_rows(min_row=2), 2):
        if row_idx % 2 == 0:
            for cell in row:
                cell.fill = light_fill