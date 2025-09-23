import pandas as pd
from pathlib import Path
import importlib

def test_icici_parser_e2e():
    root = Path(__file__).resolve().parent.parent
    pdf = root / 'data' / 'icici' / 'icici_sample.pdf'
    csv = root / 'data' / 'icici' / 'icici_sample.csv'
    mod = importlib.import_module('custom_parsers.icici_parser')
    df = mod.parse(str(pdf))
    expected = pd.read_csv(csv)
    for c in expected.columns:
        if any(k in c.lower() for k in ['amount','debit','credit','balance']):
            expected[c] = pd.to_numeric(expected[c].astype(str).str.replace(',','').str.replace('(','-').str.replace(')',''), errors='coerce')
    assert list(df.columns) == list(expected.columns)
    assert df.equals(expected)
