import pandas as pd

def normalize_amount_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "").str.replace("(", "-").str.replace(")", ""),
        errors="coerce"
    )
