import pandas as pd
import pdfplumber
import sys


def parse(pdf_path: str) -> pd.DataFrame:
    pdf = pdfplumber.open(pdf_path)
    rows = []
    
    for page in pdf.pages:
        tables = page.extract_tables()
        if tables:
            for table in tables:
                for row in table:
                    # Skip header rows and empty rows
                    if row and len(row) >= 5:
                        # Skip if first cell is empty, None, or contains 'Date'
                        if row[0] and row[0].strip() and 'Date' not in str(row[0]):
                            # Skip if Description column contains 'Description' header
                            if row[1] and str(row[1]).strip() != 'Description':
                                rows.append(row)
        else:
            text = page.extract_text()
            lines = text.split('\n')
            date_tokens = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y']
            for line in lines:
                # Skip empty lines and header lines
                if not line.strip() or 'Date' in line or 'Description' in line:
                    continue
                    
                for token in date_tokens:
                    try:
                        if pd.to_datetime(line.split()[0], format=token, errors='coerce') is not pd.NaT:
                            parts = line.split()
                            date = parts[0]
                            balance = None
                            credit = None
                            debit = None
                            description = None
                            
                            # Extract numeric values from right to left
                            numeric_parts = []
                            for part in reversed(parts):
                                if part.replace('.', '', 1).replace('-', '', 1).replace(',', '').isdigit():
                                    numeric_parts.append(part)
                            
                            if len(numeric_parts) >= 1:
                                balance = numeric_parts[0]
                            if len(numeric_parts) >= 2:
                                credit = numeric_parts[1]  
                            if len(numeric_parts) >= 3:
                                debit = numeric_parts[2]
                                
                            # Extract description (everything between date and numbers)
                            desc_parts = parts[1:len(parts) - len(numeric_parts)]
                            description = ' '.join(desc_parts) if desc_parts else ''
                            
                            rows.append([date, description, debit, credit, balance])
                            break
                    except:
                        continue
    
    if not rows:
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])
    
    df = pd.DataFrame(rows, columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])
    
    # Additional header cleanup
    df = df[df['Date'].notna()]  # Remove rows with NaN dates
    df = df[df['Date'] != '']    # Remove rows with empty dates  
    df = df[df['Description'] != 'Description']  # Remove header repeats
    df = df[~df['Date'].str.contains('Date', na=False)]  # Remove any 'Date' headers
    
    # Reset index after filtering
    df = df.reset_index(drop=True)
    
    # Normalize dates with specific format to avoid warnings
    df['Date'] = pd.to_datetime(df['Date'], format='%d-%m-%Y', errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y')
    df['Description'] = df['Description'].str.strip()
    
    # Clean numeric columns
    for c in df.columns:
        cl = c.lower()
        if any(k in cl for k in ['amount', 'debit', 'credit', 'balance']):
            df[c] = (df[c].astype(str)
                     .str.replace(',', '', regex=False)
                     .str.replace('(', '-', regex=False)
                     .str.replace(')', '', regex=False)
                     .str.replace('None', '', regex=False))  # Handle None values
            df[c] = pd.to_numeric(df[c], errors='coerce')
    
    return df


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python icici_parser.py <input.pdf> <output.csv>")
        sys.exit(1)
        
    in_pdf, out_csv = sys.argv[1], sys.argv[2]
    df = parse(in_pdf)
    df.to_csv(out_csv, index=False)
    print(f"Parsed {len(df)} rows to {out_csv}")
