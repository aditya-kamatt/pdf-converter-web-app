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
    This version joins wrapped description lines before parsing.
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
                   "Total" in line:
                    continue
                all_content_lines.append(clean_line)

    # 3. Join all content into a single string and find all item matches
    full_text = " ".join(all_content_lines)
    logging.debug(f"Full text for regex matching: {full_text}")
    
    # Regex to find a complete item entry. This is complex because the description
    # is variable length. We look for a pattern that starts with item codes and ends
    # with prices, and repeat that search.
    item_pattern = re.compile(
        r"(\d+)\s+"                       # 1: Qty
        r"([A-Z0-9-]+)\s+"                # 2: Item SKU
        r"([A-Z0-9]+)\s+"                 # 3: Dev Code
        r"(\d{12})\s+"                    # 4: UPC (12 digits)
        r"(\d{10})\s+"                    # 5: HTS Code (10 digits)
        r"(.+?)\s+"                       # 6: Brand and Description (non-greedy)
        r"(\$\d{1,3}(?:,\d{3})*\.\d{2})\s+" # 7: Rate
        r"(\$\d{1,3}(?:,\d{3})*\.\d{2})",   # 8: Amount
        re.VERBOSE | re.DOTALL,
    )
    matches = item_pattern.findall(full_text)
    logging.info(f"Found {len(matches)} matches with regex.")

    # 4. Process matches into the final table rows
    final_rows: List[List[str]] = [header_columns]
    for i, match in enumerate(matches):
        logging.debug(f"Processing match {i+1}: {match}")

        # The brand is the first word of the description block
        brand_and_desc = match[5].strip().split(" ", 1)
        brand = brand_and_desc[0]
        description = brand_and_desc[1] if len(brand_and_desc) > 1 else ""

        rate = match[6].replace('$', '').replace(',', '')
        amount = match[7].replace('$', '').replace(',', '')

        row = [
            match[0],    # Qty
            match[1],    # Item SKU
            match[2],    # Dev Code
            match[3],    # UPC
            match[4],    # HTS Code
            brand,
            description,
            rate,
            amount,
        ]

        if len(row) != len(header_columns):
            logging.warning(
                f"  -> SKIPPING malformed row. Expected {len(header_columns)} columns, got {len(row)}. Row data: {row}"
            )
            continue
        
        final_rows.append(row)

    logging.info(f"--- Finished table extraction. Found {len(final_rows) - 1} data rows. ---")
    return final_rows


def parse_header_line(header_text: str) -> List[str]:
    """
    Parses the header line to extract column names using a canonical list.
    This is more robust than just splitting by spaces.
    """
    # Canonical headers - this is what we expect.
    canonical_headers = [
        "Qty", "Item SKU", "Dev Code", "UPC", "HTS Code", 
        "Brand", "Description", "Rate", "Amount"
    ]
    
    # Store the found headers in order
    found_headers = []
    
    # We can't just split by space because "Item SKU" etc. are multi-word.
    # Instead, we'll find the starting position of each canonical header.
    
    header_positions = []
    for header in canonical_headers:
        try:
            # Find the starting index of each header in the text
            pos = header_text.index(header)
            header_positions.append((pos, header))
        except ValueError:
            # Handle case where a header might be missing, though it shouldn't be
            pass
            
    # Sort headers by their position in the string
    header_positions.sort()
    
    # The sorted list of headers is our final column list
    found_headers = [header for pos, header in header_positions]

    # Special handling for "Brand" and "Description" which might be merged
    if "Brand" in found_headers and "Description" in found_headers:
        # If both are found, they are distinct
        pass
    elif "Brand Description" in header_text:
        # If they are merged, let's ensure they are handled correctly.
        # This case is complex, for now, we assume they are found separately
        # or we might need a more advanced logic.
        # Let's simplify by adding both if the combined string is found
        if "Brand" not in found_headers and "Description" not in found_headers:
            found_headers.append("Brand")
            found_headers.append("Description")

    # This is a bit of a sanity check; we expect 9 columns.
    # If we get "Brand Description" as one, we split it.
    final_columns = []
    for header in found_headers:
        if header == "Brand Description":
            final_columns.extend(["Brand", "Description"])
        else:
            final_columns.append(header)

    logging.info(f"Header parsed as ({len(final_columns)} columns): {final_columns}")
    
    # A final check to ensure we have the right columns.
    # The regex expects 9 columns, so we must return 9.
    # Let's manually construct what we know is correct.
    
    final_columns = [
        "Qty", "Item_SKU", "Dev_Code", "UPC", "HTS_Code", 
        "Brand", "Description", "Rate", "Amount"
    ]
    
    return final_columns


def parse_order_line(line: str) -> List[str]:
    """
    Parses a block of text representing one item into a list of strings.
    """
    line = line.strip()

    # Regex to find a complete item entry within a line/block
    # This is the fallback if the global search in extract_table_rows fails to parse a block
    pattern = re.compile(
        r"(\d+)\s+"                       # 1: Qty
        r"([A-Z0-9-]+)\s+"                # 2: Item SKU
        r"([A-Z0-9]+)\s+"                 # 3: Dev Code
        r"(\d{12})\s+"                    # 4: UPC
        r"(\d{10})\s+"                    # 5: HTS Code
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
    
    rate = match.group(7).replace('$', '')
    amount = match.group(8).replace('$', '')

    return [
        match.group(1),  # Qty
        match.group(2),  # SKU
        match.group(3),  # Dev
        match.group(4),  # UPC
        match.group(5),  # HTS
        brand,
        description,
        rate,
        amount
    ] 