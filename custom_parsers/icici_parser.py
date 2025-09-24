
import pdfplumber
import pandas as pd
import re
import sys

# Define the exact columns required for the output DataFrame
REQUIRED_COLUMNS = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']

# Regular expression to match various date formats at the beginning of a line
# Supported formats: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD Mon YYYY (e.g., 01 Aug 2024)
MONTH_ABBR = r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
DATE_REGEX = re.compile(
    r'^(?:'  # Non-capturing group for the start of various date patterns
    r'\d{1,2}[-/]\d{1,2}[-/]\d{4}|'  # DD/MM/YYYY or DD-MM-YYYY
    r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|'  # YYYY-MM-DD
    r'\d{1,2} ' + MONTH_ABBR + r' \d{4}' # DD Mon YYYY
    r')',
    re.IGNORECASE # To match 'Aug' or 'aug' etc.
)

# Keywords for robust header matching in tables (lowercase for comparison)
DATE_KEYWORDS = ['date', 'txn date', 'transaction date', 'value date', 'posting date']
DESC_KEYWORDS = ['description', 'particulars', 'narration', 'details', 'remark', 'transaction', 'notes']
DEBIT_KEYWORDS = ['debit', 'withdrawal', 'dr amt', 'amount dr', 'withdrawals']
CREDIT_KEYWORDS = ['credit', 'deposit', 'cr amt', 'amount cr', 'deposits']
BALANCE_KEYWORDS = ['balance', 'running balance', 'closing balance', 'avail balance', 'bal']

def find_header_index(header_cells, keywords):
    """
    Finds the index of a column in a header row based on a list of keywords.
    Prioritizes exact matches, then partial matches.
    """
    for i, cell_content in enumerate(header_cells):
        if cell_content is None:
            continue
        clean_cell = str(cell_content).lower().strip()
        if any(kw == clean_cell for kw in keywords): # Exact match first
            return i
    for i, cell_content in enumerate(header_cells):
        if cell_content is None:
            continue
        clean_cell = str(cell_content).lower().strip()
        if any(kw in clean_cell for kw in keywords): # Partial match
            return i
    return None

def parse(pdf_path: str) -> pd.DataFrame:
    """
    Parses a bank statement PDF and extracts transaction data into a pandas DataFrame.

    Args:
        pdf_path: The path to the PDF file.

    Returns:
        A pandas DataFrame with columns: ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'].
    """
    all_transactions = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_transactions = []

            # --- Attempt Table Extraction ---
            tables = page.extract_tables()
            
            for table in tables:
                if not table or not any(row for row in table): # Skip empty tables
                    continue

                header_map = {} # Maps REQUIRED_COLUMNS to table column indices
                data_rows = []

                if len(table) > 0:
                    # Prepare header cells for keyword matching
                    header_cells = [str(cell).strip() if cell is not None else '' for cell in table[0]]
                    
                    # Map keywords to column indices
                    header_map['Date'] = find_header_index(header_cells, DATE_KEYWORDS)
                    header_map['Description'] = find_header_index(header_cells, DESC_KEYWORDS)
                    header_map['Debit Amt'] = find_header_index(header_cells, DEBIT_KEYWORDS)
                    header_map['Credit Amt'] = find_header_index(header_cells, CREDIT_KEYWORDS)
                    header_map['Balance'] = find_header_index(header_cells, BALANCE_KEYWORDS)
                    
                    # Check if enough columns were identified to consider it a transaction table
                    # At least a Date and Description, plus one of the amount/balance columns
                    mapped_columns_count = sum(1 for col_idx in header_map.values() if col_idx is not None)
                    
                    if mapped_columns_count >= 3 and header_map.get('Date') is not None:
                        # If Date and at least two other transaction-related columns are found, consider it a valid header
                        data_rows = table[1:] # Skip header, process rest as data
                    else:
                        # Not a suitable header, this table will be ignored for structured extraction
                        data_rows = []

                for row in data_rows:
                    if not row or all(x is None or str(x).strip() == '' for x in row): # Skip empty rows
                        continue

                    txn_dict = {col: None for col in REQUIRED_COLUMNS}
                    
                    # Extract values based on mapped header indices
                    try:
                        date_val = row[header_map['Date']] if header_map.get('Date') is not None and header_map['Date'] < len(row) else None
                        desc_val = row[header_map['Description']] if header_map.get('Description') is not None and header_map['Description'] < len(row) else None
                        debit_val = row[header_map['Debit Amt']] if header_map.get('Debit Amt') is not None and header_map['Debit Amt'] < len(row) else None
                        credit_val = row[header_map['Credit Amt']] if header_map.get('Credit Amt') is not None and header_map['Credit Amt'] < len(row) else None
                        balance_val = row[header_map['Balance']] if header_map.get('Balance') is not None and header_map['Balance'] < len(row) else None
                        
                        # Basic validation: must have a date and some content for it to be a transaction
                        if date_val and str(date_val).strip() != '':
                            txn_dict['Date'] = str(date_val).strip()
                            txn_dict['Description'] = str(desc_val).strip() if desc_val else ''
                            txn_dict['Debit Amt'] = str(debit_val).strip() if debit_val else None
                            txn_dict['Credit Amt'] = str(credit_val).strip() if credit_val else None
                            txn_dict['Balance'] = str(balance_val).strip() if balance_val else None
                            page_transactions.append(txn_dict)
                    except IndexError:
                        # Row length mismatch with header map, skip this row
                        pass
            
            # If no transactions were successfully extracted from tables on this page,
            # or if the page had no suitable tables, fallback to text extraction.
            if not page_transactions:
                lines = page.extract_text().splitlines()
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    date_match = DATE_REGEX.match(line)
                    if date_match:
                        date_str = date_match.group(0).strip()
                        rest_of_line = line[len(date_str):].strip()
                        
                        # Split by 2+ spaces or tabs
                        tokens = [t for t in re.split(r'\s{2,}|\t+', rest_of_line) if t]

                        current_txn = {'Date': date_str, 'Description': '', 'Debit Amt': None, 'Credit Amt': None, 'Balance': None}
                        
                        desc_parts = []
                        debit_candidate = None
                        credit_candidate = None
                        balance_candidate = None
                        
                        num_assigned = 0 # Counter for numbers assigned from right
                        
                        # Iterate tokens from the right, assigning numbers greedily based on prompt's order:
                        # Balance (rightmost), Credit (next), Debit (next)
                        for i in range(len(tokens) - 1, -1, -1): # Iterate backwards
                            token = tokens[i]
                            # Clean token for numeric check (remove commas, handle parentheses for negative)
                            clean_token = (str(token).replace(',', '')
                                                     .replace('(', '-') # Treat (X) as -X
                                                     .replace(')', ''))
                            
                            # Check if the token looks like a number
                            is_numeric_candidate = re.match(r'^-?\d+(\.\d+)?$', clean_token)
                            
                            if is_numeric_candidate:
                                if num_assigned == 0:
                                    balance_candidate = clean_token
                                elif num_assigned == 1:
                                    credit_candidate = clean_token
                                elif num_assigned == 2:
                                    debit_candidate = clean_token
                                else: # More than 3 numbers, prepend to description
                                    desc_parts.insert(0, token)
                                num_assigned += 1
                            else:
                                # If we hit a non-numeric token, it's part of the description.
                                # Prepend it to maintain original order.
                                desc_parts.insert(0, token)
                                
                        current_txn['Balance'] = balance_candidate
                        current_txn['Credit Amt'] = credit_candidate
                        current_txn['Debit Amt'] = debit_candidate
                        current_txn['Description'] = ' '.join(desc_parts).strip()
                        
                        # Add to page transactions if we found a balance or substantial description
                        if current_txn['Balance'] is not None or current_txn['Description']:
                            page_transactions.append(current_txn)
            
            all_transactions.extend(page_transactions) # Add transactions from this page to the main list

    # Create DataFrame from collected transactions
    df = pd.DataFrame(all_transactions, columns=REQUIRED_COLUMNS)

    # --- Normalization ---

    # 1. Trim whitespace for all object (string) columns
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str.strip()

    # 2. Convert Date column to strings formatted as DD-MM-YYYY
    # Use errors='coerce' to turn unparseable dates into NaT
    # dayfirst=True to correctly parse DD-MM-YYYY or DD/MM/YYYY dates
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y')
    # `strftime('%d-%m-%Y')` on NaT results in the string 'NaT'. Replace this with None for consistency.
    df['Date'] = df['Date'].replace('NaT', None) 

    # 3. Normalize numeric columns (amount, debit, credit, balance)
    for c in df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ['amount','debit','credit','balance']):
            # Ensure column is string type before str operations
            # Remove commas, treat parentheses as negative sign, then remove them
            df[c] = (df[c].astype(str)
                         .str.replace(',', '', regex=False)
                         .str.replace('(', '-', regex=False) 
                         .str.replace(')', '', regex=False))
            # Coerce to numeric, turning non-convertible values into NaN
            df[c] = pd.to_numeric(df[c], errors='coerce')
    
    return df

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python your_module_name.py <input_pdf_path> <output_csv_path>")
        sys.exit(1)
    
    in_pdf, out_csv = sys.argv[1], sys.argv[2]
    
    print(f"Parsing '{in_pdf}'...")
    try:
        df = parse(in_pdf)
        df.to_csv(out_csv, index=False)
        print(f"Successfully parsed PDF and saved to '{out_csv}'")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
