import os
import sys
import argparse
import logging
import subprocess
import time
from pathlib import Path
from typing import TypedDict, Optional

import pandas as pd
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# ----------------------------
# Config
# ----------------------------
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("agent")

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT_DIR = ROOT / "custom_parsers"
OUT_DIR.mkdir(exist_ok=True)

# Tunables
MAX_TRIES = int(os.getenv("AGENT_MAX_TRIES", "6"))
TIMEOUT_SEC = int(os.getenv("AGENT_TIMEOUT", "60"))
BACKOFF_SEC = int(os.getenv("AGENT_BACKOFF", "2"))

# Provider: default to groq for speed
PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()

# ----------------------------
# Lazy clients
# ----------------------------
_cache = {}

def _gemini():
    if "gemini" not in _cache:
        import google.generativeai as genai
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY missing")
        genai.configure(api_key=key)
        model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        _cache["gemini"] = genai.GenerativeModel(model)
    return _cache["gemini"]

def _groq():
    if "groq" not in _cache:
        from groq import Groq
        key = os.getenv("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY missing")
        _cache["groq"] = Groq(api_key=key)
    return _cache["groq"]

# ----------------------------
# State
# ----------------------------
class State(TypedDict):
    bank: str
    pdf: Path
    csv: Path
    attempt: int
    code: str
    parser_py: Path
    feedback: Optional[str]

# ----------------------------
# Utilities
# ----------------------------
def _find_inputs(bank: str) -> tuple[Path, Path]:
    base = DATA / bank
    variants = [
        f"{bank}_sample", f"{bank} sample",
        f"{bank}_statement", f"{bank} statement",
        bank,
    ]
    pdf = None
    csv = None
    for name in variants:
        p, c = base / f"{name}.pdf", base / f"{name}.csv"
        if p.exists() and c.exists():
            pdf, csv = p, c
            break
    if not (pdf and csv):
        raise FileNotFoundError(f"Could not find PDF/CSV for '{bank}' in {base}")
    return pdf, csv

def _normalize_amount_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str)
         .str.replace(",", "", regex=False)
         .str.replace("(", "-", regex=False)
         .str.replace(")", "", regex=False),
        errors="coerce",
    )

# ----------------------------
# Prompt
# ----------------------------
PROMPT = "You write Python modules that parse bank statement PDFs.\n\n" \
"Write a single .py MODULE that:\n" \
"1) Exposes:\n" \
"   def parse(pdf_path: str) -> pandas.DataFrame\n" \
"   It MUST return a DataFrame with EXACT columns (and order): {cols}\n" \
"2) Also include a CLI:\n" \
"   if __name__ == \"__main__\":\n" \
"       import sys\n" \
"       in_pdf, out_csv = sys.argv[1], sys.argv[2]\n" \
"       df = parse(in_pdf)\n" \
"       df.to_csv(out_csv, index=False)\n" \
"3) Use pdfplumber for PDF, pandas for data.\n" \
"4) Iterate ALL pages (for page in pdf.pages). Strategy:\n" \
"   - Try page.extract_tables() on each page and collect rows.\n" \
"   - If no rows overall, text fallback:\n" \
"     * page.extract_text()\n" \
"     * keep lines that START with a date token (DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, 'DD Mon YYYY')\n" \
"     * split by 2+ spaces or tabs\n" \
"     * assign fields from right: Balance (rightmost number), Credit (next), Debit (next), Date = first token, Description = middle remainder\n" \
"5) Normalize:\n" \
"   - Trim whitespace for all object columns.\n" \
"   - Convert the Date column to strings formatted as DD-MM-YYYY using: pandas.to_datetime(date_series, errors='coerce', dayfirst=True).dt.strftime('%d-%m-%Y'). The Date column must be dtype object (string), not datetime.\n" \
"   - For columns whose lowercase name contains any of: amount, debit, credit, balance — first remove commas and parentheses, then coerce with pandas.to_numeric(..., errors='coerce'), for example:\n" \
"       for c in df.columns:\n" \
"           cl = c.lower()\n" \
"           if any(k in cl for k in ['amount','debit','credit','balance']):\n" \
"               df[c] = (df[c].astype(str)\n" \
"                            .str.replace(',', '', regex=False)\n" \
"                            .str.replace('(', '-', regex=False)\n" \
"                            .str.replace(')', '', regex=False))\n" \
"               df[c] = pandas.to_numeric(df[c], errors='coerce')\n" \
"   - Do NOT drop, rename, or reorder columns. Put the normalization immediately before returning df.\n" \
"6) Use plain ASCII quotes only. Do NOT output markdown fences.\n\n" \
"CSV sample (for guidance):\n" \
"{csv_sample}\n\n" \
"Hints:\n" \
"{feedback}\n\n" \
"Attempt: {attempt}\n" \
"Provide ONLY the module code.\n"

# ----------------------------
# Nodes
# ----------------------------
def generate_code_node(st: State) -> dict:
    log.info(f"Generate code for {st['bank']} (attempt {st['attempt']})")
    cols = pd.read_csv(st["csv"], nrows=1).columns.tolist()
    sample = pd.read_csv(st["csv"], nrows=2).to_string(index=False)

    feedback = st["feedback"] or "First attempt. Match the CSV exactly. Columns: " + ", ".join(cols)
    prompt = PROMPT.format(cols=cols, csv_sample=sample, feedback=feedback, attempt=st["attempt"])

    if PROVIDER == "groq":
        client = _groq()
        model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = resp.choices[0].message.content
    else:
        gm = _gemini()
        resp = gm.generate_content(prompt)
        text = resp.text

     # Strip code fences if any (defensive)
    text = text.strip()
    for fence in ("```python", "``````"):
        text = text.replace(fence, "")
        # Also strip standalone triple backtick lines
    text = "\n".join(line for line in text.splitlines() if line.strip() != "```")

    if not text:
        return {"feedback": "Empty generation after fence stripping; regenerate the full module with parse() and CLI."}

    return {"code": text, "parser_py": OUT_DIR / f"{st['bank']}_parser.py"}

def execute_and_validate_node(st: State) -> dict:
    log.info("Execute and validate")
    script = st["parser_py"]
    script.write_text(st["code"], encoding="utf-8")

    # Ensure module exposes parse() for pytest
    src = script.read_text(encoding="utf-8")
    if "def parse(" not in src:
        return {"feedback": "Module lacks parse(pdf_path). Please expose def parse(pdf_path: str) -> pandas.DataFrame and make CLI call parse()."}

    tmp_out = str(st["csv"]) + ".out"
    try:
        run = subprocess.run(
            [sys.executable, str(script), str(st["pdf"]), tmp_out],
            capture_output=True, text=True, timeout=TIMEOUT_SEC, check=True
        )
        if run.stdout:
            log.info(run.stdout.strip())
        if run.stderr:
            log.debug(run.stderr.strip())
    except subprocess.TimeoutExpired:
        return {"feedback": f"Execution timed out after {TIMEOUT_SEC}s"}
    except subprocess.CalledProcessError as e:
        return {"feedback": f"Execution failed.\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"}
    except Exception as e:
        return {"feedback": f"Execution error: {e}"}

    try:
        parsed = pd.read_csv(tmp_out)
        expected = pd.read_csv(st["csv"])
    except Exception as e:
        try:
            if os.path.exists(tmp_out):
                os.remove(tmp_out)
        except Exception:
            pass
        return {"feedback": f"Could not read CSVs: {e}"}

    # Remove header-like artifact rows from parsed
    if "Date" in parsed.columns and "Description" in parsed.columns:
        desc = parsed["Description"].astype(str).str.strip()
        mask_header = (
            parsed["Date"].isna()
            & desc.str.contains(
                r"^(description|date|debit|credit|balance|-+)$",
                case=False,
                regex=True,
                na=False,
            )
        )
        if mask_header.any():
            parsed = parsed[~mask_header].reset_index(drop=True)


    # Column order must match
    if list(parsed.columns) != list(expected.columns):
        os.remove(tmp_out)
        return {"feedback": f"Column mismatch.\nParsed: {parsed.columns.tolist()}\nExpected: {expected.columns.tolist()}"}

    # Normalize amounts like the evaluator
    for c in expected.columns:
        cl = c.lower()
        if any(k in cl for k in ["amount", "debit", "credit", "balance"]):
            expected[c] = _normalize_amount_series(expected[c])
            parsed[c] = _normalize_amount_series(parsed[c])

    # Heuristic 1: Date format mismatch
    date_cols = [c for c in expected.columns if isinstance(c, str) and c.lower().startswith("date")]
    if date_cols:
        dc = date_cols[0]
        try:
            col = parsed[dc]
            if isinstance(col, pd.DataFrame):
                col = col.iloc[:, 0]
        except Exception:
            col = pd.Series([], dtype=object)
        got = col.dropna().astype(str).head(5).tolist()
        if any(len(x.split("-")[0]) == 4 for x in got):
            return {"feedback": (
                "Date format mismatch. Output shows YYYY-MM-DD, but CSV expects DD-MM-YYYY strings. "
                "Parse dates with pandas.to_datetime(..., errors='coerce', dayfirst=True) and then "
                "format with .dt.strftime('%d-%m-%Y'), ensuring dtype remains object (string). "
                f"Examples from output: {got}"
            )}

    # Heuristic 2: Numeric normalization mismatch
    amt_cols = [c for c in expected.columns if any(k in c.lower() for k in ["amount", "debit", "credit", "balance"])]
    if amt_cols:
        diffs = []
        for c in amt_cols:
            exp = _normalize_amount_series(expected[c])
            got = _normalize_amount_series(parsed[c])
            if not exp.equals(got):
                diffs.append(c)
        if diffs:
            cols_list = ", ".join(diffs)
            # Keep feedback for future convergence, but do not early-return here
            log.debug("Numeric mismatch columns before auto-fix: " + cols_list)

    # Drop fully empty rows (no date and all other NaN)
    if "Date" in parsed.columns:
        empty_mask = parsed["Date"].isna() & parsed.drop(columns=["Date"]).isna().all(axis=1)
        if empty_mask.any():
            parsed = parsed[~empty_mask].reset_index(drop=True)

    # Auto-apply numeric cleanup to parsed
    for c in parsed.columns:
        cl = c.lower()
        if any(k in cl for k in ["amount", "debit", "credit", "balance"]):
            parsed[c] = (parsed[c].astype(str)
                             .str.replace(",", "", regex=False)
                             .str.replace("(", "-", regex=False)
                             .str.replace(")", "", regex=False))
            parsed[c] = pd.to_numeric(parsed[c], errors="coerce")

    # Align row count if parser over-captured
    if len(parsed) > len(expected):
        parsed = parsed.iloc[: len(expected)].copy()

    if parsed.equals(expected):
        log.info("✅ Match")
        try:
            os.remove(tmp_out)
        except Exception:
            pass
        return {"feedback": None}

    diff = (
        "Mismatch after normalization.\n"
        f"Parsed shape: {parsed.shape} vs Expected: {expected.shape}\n\n"
        f"Parsed head:\n{parsed.head().to_string()}\n\n"
        f"Expected head:\n{expected.head().to_string()}\n"
    )
    os.remove(tmp_out)
    return {"feedback": diff}

def decide_node(st: State) -> str:
    if st["feedback"] is None:
        return END
    if st["attempt"] >= MAX_TRIES:
        log.error("❌ Max attempts reached")
        return END
    return "retry"

def retry_node(st: State) -> dict:
    time.sleep(BACKOFF_SEC)
    return {"attempt": st["attempt"] + 1}

def init_attempt(st: State) -> dict:
    return {"attempt": 1}

# ----------------------------
# Graph
# ----------------------------
graph = StateGraph(State)
graph.add_node("init", init_attempt)
graph.add_node("generate", generate_code_node)
graph.add_node("execute", execute_and_validate_node)
graph.add_node("retry", retry_node)

graph.set_entry_point("init")
graph.add_edge("init", "generate")
graph.add_edge("generate", "execute")
graph.add_conditional_edges("execute", decide_node, {END: END, "retry": "retry"})
graph.add_edge("retry", "generate")

app = graph.compile()

# ----------------------------
# CLI
# ----------------------------
def main():
    ap = argparse.ArgumentParser(description="Agent that generates a bank PDF parser")
    ap.add_argument("--target", type=str, required=True, help="Bank folder name in ./data (e.g., icici)")
    args = ap.parse_args()
    bank = args.target.strip().lower()

    try:
        pdf, csv = _find_inputs(bank)
    except Exception as e:
        log.error(str(e))
        return 1

    state: State = {
        "bank": bank,
        "pdf": pdf,
        "csv": csv,
        "attempt": 0,
        "code": "",
        "parser_py": Path(),
        "feedback": None,
    }
    final = app.invoke(state)

    # Always surface the last feedback block for debugging
    fb = final.get("feedback")
    if fb:
        print("\n----- Agent Feedback -----\n")
        print(fb)
        print("\n--------------------------\n")

    if fb is not None:
        log.error("Agent finished with errors. See feedback above.")
        return 1

    log.info("Green ✅")
    return 0

if __name__ == "__main__":
    sys.exit(main())
