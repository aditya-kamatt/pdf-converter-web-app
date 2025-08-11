 import re
import logging
from typing import List, Dict, Any

import pdfplumber


def extract_header_meta(pdf_path: str) -> Dict[str, Any]:
    """Extracts metadata from the first page of the PDF."""
    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            return {}
        first_page = pdf.pages[0]
        text = first_page.extract_text(x_tolerance=2, y_tolerance=2) or ""

        po_number_match = re.search(r'PO ?(\d{6,})', text)
        ship_by_date_match = re.search(r'SHIP COMPLETE BY DATE:\s*(\d{1,2}/\d{1,2}/\d{4})', text)
        payment_terms_match = re.search(r'PAYMENT TERMS:\s*(.*)', text)

        vendor_number = "N/A"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            # Case where number is on the same line, e.g. "Vendor # 12345"
            if "Vendor #" in line:
                match = re.search(r'Vendor #\s*(\d+)', line)
                if match:
                    vendor_number = match.group(1)
                    break
                # Case where number is on the line below "Vendor #"
                elif i + 1 < len(lines):
                    next_line = lines[i+1].strip()
                    # Match a line that starts with digits
                    match = re.match(r'^(\d+)', next_line)
                    if match:
                        vendor_number = match.group(1)
                        break

        total_match = None
        # Search for Total on the last few pages as it's typically at the end
        for page in reversed(pdf.pages):
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            total_match = re.search(r'Total\s+\$(\d{1,3}(?:,\d{3})*\.\d{2})', page_text)
            if total_match:
                break

        meta = {
            "po_number": po_number_match.group(1) if po_number_match else "N/A",
            "vendor_number": vendor_number,
            "ship_by_date": ship_by_date_match.group(1) if ship_by_date_match else "N/A",
            "payment_terms": payment_terms_match.group(1).strip() if payment_terms_match else "N/A",
            "total": total_match.group(1) if total_match else "N/A",
            "page_count": len(pdf.pages)
        }
        return meta


def extract_table_rows(pdf_path: str) -> List[List[str]]:
    """
    Extracts all table rows from all pages of the PDF.
    Improved version to handle missing HTS codes and various formats.
    """
    logging.info("--- Starting table extraction ---")
    header_columns: List[str] = []
    header_line_text = ""

    # 1. Find the canonical header text and columns from the first page with a valid header
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if not text:
                continue
            for line in text.split('\n'):
                if "Qty" in line and "Item SKU" in line:
                    header_line_text = line.strip()
                    header_columns = parse_header_line(header_line_text)
                    logging.info(f"Found canonical header on page {page_num}: '{header_line_text}'")
                    break
            if header_columns:
                break

    if not header_columns:
        logging.warning("Could not find a header row in the PDF. Aborting table extraction.")
        return []

    logging.info(f"Header parsed as: {header_columns}")

    # 2. Collect all non-header/footer lines from all pages
    all_content_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text(x_tolerance=2, y_tolerance=2) or ""
            if not text:
                continue

            lines = text.split('\n')
            for line in lines:
                clean_line = line.strip()
                # Skip blank lines, header lines, or footer-like lines
                if not clean_line or \
                   clean_line == header_line_text or \
                   ("Qty" in clean_line and "Item SKU" in clean_line) or \
                   "This Purchase Order" in clean_line or \
                   "Page " in clean_line or \
                   clean_line.startswith("Total") or \
                   "TERMS:" in clean_line or \
                   clean_line.startswith("PO001954") or \
                   "of 17" in clean_line:
                    continue
                all_content_lines.append(clean_line)

    # 3. Join all content and parse with improved regex patterns
    full_text = " ".join(all_content_lines)
    logging.debug(f"Full text length: {len(full_text)} characters")
    
    # Multiple regex patterns to handle different formats
    patterns = [
        # Pattern 1: Complete with HTS Code
        re.compile(
            r"(\d+)\s+"                           # 1: Qty
            r"([A-Z0-9-]+)\s+"                    # 2: Item SKU
            r"([A-Z0-9]+)\s+"                     # 3: Dev Code
            r"(\d{12})\s+"                        # 4: UPC (12 digits)
            r"(\d{10})\s+"                        # 5: HTS Code (10 digits)
            r"([A-Za-z][A-Za-z0-9\s&'-]+?)\s+"   # 6: Brand and Description (starts with letter)
            r"(\$\d{1,3}(?:,\d{3})*\.\d{2})\s+"  # 7: Rate
            r"(\$\d{1,3}(?:,\d{3})*\.\d{2})",    # 8: Amount
            re.VERBOSE
        ),
        # Pattern 2: Missing HTS Code
        re.compile(
            r"(\d+)\s+"                           # 1: Qty
            r"([A-Z0-9-]+)\s+"                    # 2: Item SKU
            r"([A-Z0-9]+)\s+"                     # 3: Dev Code
            r"(\d{12})\s+"                        # 4: UPC (12 digits)
            r"([A-Za-z][A-Za-z0-9\s&'-]+?)\s+"   # 5: Brand and Description (no HTS)
            r"(\$\d{1,3}(?:,\d{3})*\.\d{2})\s+"  # 6: Rate
            r"(\$\d{1,3}(?:,\d{3})*\.\d{2})",    # 7: Amount
            re.VERBOSE
        )
    ]
    
    final_rows: List[List[str]] = [header_columns]
    found_items = set()  # To avoid duplicates
    
    for pattern_idx, pattern in enumerate(patterns):
        matches = pattern.findall(full_text)
        logging.info(f"Pattern {pattern_idx + 1} found {len(matches)} matches")
        
        for match in matches:
            try:
                if pattern_idx == 0:  # Complete pattern with HTS
                    qty, sku, dev_code, upc, hts_code, brand_desc, rate, amount = match
                    
                    # Split brand and description
                    brand_desc_parts = brand_desc.strip().split(None, 1)
                    brand = brand_desc_parts[0] if brand_desc_parts else ""
                    description = brand_desc_parts[1] if len(brand_desc_parts) > 1 else ""
                    
                    # Create identifier to avoid duplicates
                    identifier = f"{qty}-{sku}-{dev_code}-{upc}"
                    if identifier in found_items:
                        continue
                    found_items.add(identifier)
                    
                    row = [
                        qty, sku, dev_code, upc, hts_code,
                        brand, description,
                        rate.replace('$', '').replace(',', ''),
                        amount.replace('$', '').replace(',', '')
                    ]
                    
                elif pattern_idx == 1:  # Pattern without HTS
                    qty, sku, dev_code, upc, brand_desc, rate, amount = match
                    
                    # Split brand and description
                    brand_desc_parts = brand_desc.strip().split(None, 1)
                    brand = brand_desc_parts[0] if brand_desc_parts else ""
                    description = brand_desc_parts[1] if len(brand_desc_parts) > 1 else ""
                    
                    # Create identifier to avoid duplicates
                    identifier = f"{qty}-{sku}-{dev_code}-{upc}"
                    if identifier in found_items:
                        continue
                    found_items.add(identifier)
                    
                    row = [
                        qty, sku, dev_code, upc, "",  # Empty HTS Code
                        brand, description,
                        rate.replace('$', '').replace(',', ''),
                        amount.replace('$', '').replace(',', '')
                    ]
                
                if len(row) != len(header_columns):
                    logging.warning(f"Skipping malformed row: expected {len(header_columns)}, got {len(row)}")
                    continue
                
                final_rows.append(row)
                logging.debug(f"Added row: {row[:3]}...")  # Log first 3 fields
                
            except Exception as e:
                logging.warning(f"Error processing match: {e}")
                continue

    logging.info(f"--- Finished table extraction. Found {len(final_rows) - 1} data rows. ---")
    return final_rows


def parse_header_line(header_text: str) -> List[str]:
    """
    Parses the header line to extract column names using a canonical list.
    """
    # Return the standard column structure
    return [
        "Qty", "Item_SKU", "Dev_Code", "UPC", "HTS_Code", 
        "Brand", "Description", "Rate", "Amount"
    ]


def parse_order_line(line: str) -> List[str]:
    """
    Parses a block of text representing one item into a list of strings.
    """
    line = line.strip()

    # Try complete pattern first
    pattern = re.compile(
        r"(\d+)\s+"                       # 1: Qty
        r"([A-Z0-9-]+)\s+"                # 2: Item SKU
        r"([A-Z0-9]+)\s+"                 # 3: Dev Code
        r"(\d{12})\s+"                    # 4: UPC
        r"(\d{10})?\s*"                   # 5: HTS Code (optional)
        r"(.+?)\s+"                       # 6: Brand and Description
        r"(\$\d{1,3}(?:,\d{3})*\.\d{2})\s+" # 7: Rate
        r"(\$\d{1,3}(?:,\d{3})*\.\d{2})"    # 8: Amount
    )
    match = pattern.search(line)

    if not match:
        return []

    # Separate brand and description
    brand_and_desc = match.group(6).strip()
    parts = brand_and_desc.split(" ", 1)
    brand = parts[0]
    description = parts[1] if len(parts) > 1 else ""
    
    rate = match.group(7).replace('$', '').replace(',', '')
    amount = match.group(8).replace('$', '').replace(',', '')
    hts_code = match.group(5) if match.group(5) else ""

    return [
        match.group(1),  # Qty
        match.group(2),  # SKU
        match.group(3),  # Dev
        match.group(4),  # UPC
        hts_code,        # HTS (may be empty)
        brand,
        description,
        rate,
        amount
    ]


def extract_data_from_pdf(pdf_path: str):
    """
    Main function to extract both metadata and table data from PDF.
    Returns (meta_dict, dataframe)
    """
    import pandas as pd
    
    # Extract metadata
    meta = extract_header_meta(pdf_path)
    
    # Extract table rows
    rows = extract_table_rows(pdf_path)
    
    if not rows or len(rows) <= 1:
        raise ValueError("No data rows found in PDF")
    
    # Convert to DataFrame
    header = rows[0]
    data_rows = rows[1:]
    df = pd.DataFrame(data_rows, columns=header)
    
    return meta, df  ] 
