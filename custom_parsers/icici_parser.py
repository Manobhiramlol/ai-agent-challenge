
import pdfplumber
import pandas
import re
import sys

# --- Constants ---
TARGET_COLUMNS = ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']

# --- Regex patterns for date detection ---
# Matches DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, DD Mon YYYY (e.g., 01 Aug 2024)
# Captures the full date string at the beginning of a line.
DATE_FULL_REGEX = re.compile(
    r'^(\d{1,2}[/-]\d{1,2}[/-]\d{4}|'  # DD/MM/YYYY or DD-MM-YYYY
    r'\d{4}[/-]\d{1,2}[/-]\d{1,2}|'    # YYYY-MM-DD or YYYY/MM/DD
    r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})',  # DD Mon YYYY
    re.IGNORECASE
)

# --- Helper Functions ---
def _starts_with_date(line: str) -> re.Match | None:
    """
    Checks if a line starts with a date pattern and returns the match object.
    """
    return DATE_FULL_REGEX.match(line)

def _is_valid_amount_str(s: str) -> bool:
    """
    Checks if a string can be converted to a numeric value, excluding specific
    non-numeric indicators like 'NaN', 'N/A', or '-' if they are the sole content.
    """
    s_clean = str(s).strip().replace(',', '').replace('(', '-').replace(')', '')
    if not s_clean:  # Empty string after cleaning
        return False
    if s_clean.lower() in ('nan', 'n/a', '-'):  # Exclude explicit non-numbers
        return False
    try:
        float(s_clean)
        return True
    except ValueError:
        return False

# --- Main Parsing Function ---
def parse(pdf_path: str) -> pandas.DataFrame:
    """
    Parses a bank statement PDF and returns a pandas.DataFrame with transaction data.

    It first attempts to extract data from tables using pdfplumber's `extract_tables()`.
    If no meaningful data is found from tables, it falls back to text extraction,
    looking for lines starting with a date and parsing fields based on whitespace.

    Args:
        pdf_path (str): The path to the PDF file.

    Returns:
        pandas.DataFrame: A DataFrame with the exact columns and order:
                          ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'].
    """
    all_collected_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        # --- Attempt 1: Table Extraction ---
        mapped_table_data = []
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                if not table:
                    continue

                header_row_candidate = table[0]
                data_rows_start_idx = 0
                
                # Check if the first row is a potential header (contains non-empty string cells)
                if header_row_candidate and any(str(cell).strip() for cell in header_row_candidate):
                    data_rows_start_idx = 1  # Skip first row as header
                    
                    col_map = {}
                    # Map header names to TARGET_COLUMNS (case-insensitive, space-agnostic)
                    for i, h_cell in enumerate(header_row_candidate):
                        h_cell_str = str(h_cell).lower().replace(' ', '')
                        if 'date' in h_cell_str: col_map['Date'] = i
                        elif 'description' in h_cell_str: col_map['Description'] = i
                        elif 'debit' in h_cell_str or 'withdrawal' in h_cell_str: col_map['Debit Amt'] = i
                        elif 'credit' in h_cell_str or 'deposit' in h_cell_str: col_map['Credit Amt'] = i
                        elif 'balance' in h_cell_str: col_map['Balance'] = i
                    
                    # Only use this table's data if we found enough meaningful header mappings.
                    # Requiring 'Date' and 'Balance' mapping as minimum for a transaction table.
                    if 'Date' in col_map and 'Balance' in col_map:
                        for row_data in table[data_rows_start_idx:]:
                            if not row_data or not any(str(c).strip() for c in row_data): # Skip completely empty rows
                                continue
                            
                            processed_row_dict = {col: None for col in TARGET_COLUMNS}
                            for target_col, original_idx in col_map.items():
                                if original_idx < len(row_data):
                                    processed_row_dict[target_col] = row_data[original_idx]
                            
                            # Append the row, ensuring TARGET_COLUMNS order
                            mapped_table_data.append([processed_row_dict[tc] for tc in TARGET_COLUMNS])
        
        if mapped_table_data:
            all_collected_rows = mapped_table_data
        else:
            # --- Fallback: Text Extraction ---
            text_based_rows = []
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    date_match = _starts_with_date(line)
                    if date_match:
                        date_str = date_match.group(0).strip()
                        remainder = line[len(date_str):].strip()

                        # Split remainder by 2+ spaces or tabs
                        parts = [p.strip() for p in re.split(r'\s{2,}|(?:\t)+', remainder) if p.strip()]

                        date_val = date_str
                        description_val = None
                        debit_amt_val = None
                        credit_amt_val = None
                        balance_val = None
                        
                        # Parse from right to left for amounts: Balance, Credit, Debit
                        # `temp_amounts_reversed` will store amounts in order [Balance, Credit, Debit]
                        temp_amounts_reversed = [] 
                        desc_split_point = len(parts) # Index in `parts` where description ends and amounts begin

                        for k in reversed(range(len(parts))):
                            if _is_valid_amount_str(parts[k]):
                                temp_amounts_reversed.append(parts[k])
                                desc_split_point = k # Description ends just before this part
                            else:
                                # If we hit a non-amount part, assume it's part of the description
                                # and stop looking for amounts at the right.
                                break 
                        
                        # Assign Balance (rightmost), then Credit (next), then Debit (next)
                        if len(temp_amounts_reversed) >= 1:
                            balance_val = temp_amounts_reversed[0]
                        if len(temp_amounts_reversed) >= 2:
                            credit_amt_val = temp_amounts_reversed[1]
                        if len(temp_amounts_reversed) >= 3:
                            debit_amt_val = temp_amounts_reversed[2]
                        
                        # The description is formed by the parts before the `desc_split_point`
                        description_parts = parts[:desc_split_point]
                        description_val = ' '.join(description_parts).strip()
                        
                        text_based_rows.append([date_val, description_val, debit_amt_val, credit_amt_val, balance_val])
            
            all_collected_rows = text_based_rows
    
    # Create DataFrame from collected rows. If no rows, it will be empty.
    df = pandas.DataFrame(all_collected_rows, columns=TARGET_COLUMNS)

    # --- Normalization ---
    # Trim whitespace for all object columns
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str.strip()

    # Convert Date column to DD-MM-YYYY string format
    # Use errors='coerce' for invalid dates, then fill NaT (Not a Time) with empty string
    # before converting to 'object' dtype (string).
    df['Date'] = pandas.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y')
    df['Date'] = df['Date'].fillna('').astype(str)

    # Normalize amount columns (Debit Amt, Credit Amt, Balance)
    for c in df.columns:
        cl = str(c).lower() # Convert column name to string and then lowercase for keyword check
        if any(k in cl for k in ['amount', 'debit', 'credit', 'balance']):
            df[c] = (df[c].astype(str) # Ensure column is string type for string operations
                         .str.replace(',', '', regex=False) # Remove commas
                         .str.replace('(', '-', regex=False) # Replace opening parenthesis with minus for negatives
                         .str.replace(')', '', regex=False)) # Remove closing parenthesis
            df[c] = pandas.to_numeric(df[c], errors='coerce') # Coerce to numeric, convert errors to NaN
    
    return df

# --- CLI Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python your_module_name.py <input_pdf_path> <output_csv_path>")
        sys.exit(1)
    
    input_pdf_path = sys.argv[1]
    output_csv_path = sys.argv[2]
    
    try:
        df_result = parse(input_pdf_path)
        df_result.to_csv(output_csv_path, index=False)
        print(f"Successfully parsed '{input_pdf_path}' and saved to '{output_csv_path}'")
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)
