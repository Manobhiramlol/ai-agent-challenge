import pandas as pd
import re

GOT = "out.csv"  # change if needed
EXP = "data/icici/icici_sample.csv"  # change if needed

def load_and_clean(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Remove header-like artifact rows (same as validator)
    if "Date" in df.columns and "Description" in df.columns:
        desc = df["Description"].astype(str).str.strip()
        mask_header = (
            df["Date"].isna()
            & desc.str.contains(r"^(description|date|debit|credit|balance|-+)$", case=False, regex=True, na=False)
        )
        if mask_header.any():
            df = df[~mask_header].reset_index(drop=True)
    return df

def main():
    got = load_and_clean(GOT)
    print("== out.csv checks ==")
    print("Shape:", got.shape)
    print("Columns:", list(got.columns))
    print("\nHead (10):\n", got.head(10).to_string(index=False))

    # Date format check
    dates = got["Date"].dropna().astype(str).head(10).tolist()
    print("\nDate samples:", dates)
    all_ddmmyyyy = all(re.match(r"^\d{2}-\d{2}-\d{4}$", s) for s in dates)
    print("All DD-MM-YYYY:", all_ddmmyyyy)

    # Numeric dtype check
    for c in ["Debit Amt", "Credit Amt", "Balance"]:
        print(c, "dtype:", got[c].dtype, "nulls:", got[c].isna().sum())

    # Compare to expected if exists
    try:
        exp = pd.read_csv(EXP)
        print("\n== compare to expected ==")
        print("Shapes equal:", got.shape == exp.shape)
        print("Columns equal/order:", list(got.columns) == list(exp.columns))
        print("Exact match:", got.equals(exp))
        if not got.equals(exp):
            diff_rows = (got != exp).any(axis=1)
            print("\nFirst differing rows (got | expected):")
            print(pd.concat([got[diff_rows].head(), exp[diff_rows].head()], axis=1))
    except FileNotFoundError:
        print("\nExpected CSV not found; skipped exact comparison.")

if __name__ == "__main__":
    main()
