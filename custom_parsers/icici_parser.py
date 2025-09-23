
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
                rows.extend(table)
        else:
            text = page.extract_text()
            lines = text.split('\n')
            date_tokens = ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y']
            for line in lines:
                for token in date_tokens:
                    if line.startswith(pd.to_datetime(line.split()[0], format=token, errors='coerce')):
                        parts = line.split()
                        date = parts[0]
                        balance = None
                        credit = None
                        debit = None
                        description = None
                        for part in reversed(parts):
                            if part.replace('.', '', 1).replace('-', '', 1).isdigit():
                                if balance is None:
                                    balance = part
                                elif credit is None:
                                    credit = part
                                elif debit is None:
                                    debit = part
                            else:
                                if description is None:
                                    description = ' '.join(parts[1:len(parts) - len([x for x in reversed(parts) if x.replace('.', '', 1).replace('-', '', 1).isdigit()])])
                        rows.append([date, description, debit, credit, balance])
    
    if not rows:
        return pd.DataFrame(columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])
    
    df = pd.DataFrame(rows, columns=['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance'])
    
    # Normalize
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y')
    df['Description'] = df['Description'].str.strip()
    for c in df.columns:
        cl = c.lower()
        if any(k in cl for k in ['amount', 'debit', 'credit', 'balance']):
            df[c] = (df[c].astype(str)
                     .str.replace(',', '', regex=False)
                     .str.replace('(', '-', regex=False)
                     .str.replace(')', '', regex=False))
            df[c] = pd.to_numeric(df[c], errors='coerce')
    
    return df

if __name__ == "__main__":
    in_pdf, out_csv = sys.argv[1], sys.argv[2]
    df = parse(in_pdf)
    df.to_csv(out_csv, index=False)