# Agent-as-Coder: Bank Statement PDF Parser Generator

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent-green.svg)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq-Llama--3.3--70B-orange.svg)](https://groq.com)

> An autonomous AI agent that automatically generates custom bank statement PDF parsers through self-correcting loops with exact DataFrame validation.

## 🎯 Challenge Overview

This project implements the **"Agent-as-Coder" Challenge** - developing a coding agent that writes custom parsers for bank statement PDFs. When run via CLI, it analyzes sample data and generates a parser in `custom_parsers/` that can process similar statements with zero manual intervention.

## 🏗️ Agent Architecture

The agent operates as a **LangGraph state machine** with autonomous self-correction:
```
┌─────────────────────┐        ┌────────────────────┐        ┌─────────────────────┐        ┌─────────────────────┐
│                     │        │                    │        │                     │        │                     │
│    Initialize       │──────▶│   Generate         │──────▶ │  Execute & Test     │──────▶│     Success?        |
│    (attempt=1)      │        │   Parser Code      │        │  (DataFrame.eq)     │        │                     │
│                     │        │                    │        │                     │        │                     │
└─────────────────────┘        └────────────────────┘        └─────────────────────┘        └─────────────────────┘
         ▲                                                                                              │
         │                                                                                              │
         │                                                                                              │ No
         │                                                                                              │
         │                      ┌─────────────────────┐                                                 │
         │                      │                     │                                                 │
         └──────────────────────│   Self-Correct      │◀───────────────────────────────────────────────┘
                                │   (≤6 attempts)     │
                                │   Targeted fixes    │
                                │                     │
                                └─────────────────────┘
                                          │
                                          │
                                          │ Max attempts reached
                                          │ or Success
                                          │
                                          ▼
                                ┌─────────────────────┐
                                │                     │
                                │        END          │
                                │    (Success         │
                                │    or Fail)         │
                                │                     │
                                └─────────────────────┘


```
**Agent Flow**: 

1. **Initialization:** "system initializes with attempt tracking"

2. **Code Generation:** "prompts Groq's `Llama-3.3-70B` to generate `custom_parsers/<bank>_parser.py`"

3. **Execution:** "executes the parser on sample PDFs"

4. **Validation:** "compares output to reference CSV using `DataFrame.equals()`"

5. **Self-Correction:** "analyzes specific issues (date formats, numeric normalization, header artifacts)"

6. **Iterative Process:** "targeted code fixes in subsequent iterations"

7. **Termination Conditions:** "until exact equality or attempt exhaustion"

--- 
## 🚀 Quick Start

### Prerequisites

- `Python 3.10+`
- Free Groq API key from [groq.com](https://groq.com)

### 5-Step Setup

**1. Clone and Install**

- `git clone https://github.com/Manobhiramlol/ai-agent-challenge.git`

- `cd ai-agent-challenge`

- `pip install -r requirements.txt` / `pip install --no-cache-dir -r requirements.txt`

---

**2. Configure Environment**

- `cp .env.example .env`

  - Edit `.env` and set:

- `GROQ_API_KEY=your_groq_api_key_here`

- `LLM_PROVIDER=groq`

- `GROQ_MODEL=llama-3.3-70b-versatile`

---
**3. Verify Sample Data**

- Ensure these exist (included in repo):

1. `ls data/icici/icici_sample.pdf`

2. `ls data/icici/icici_sample.csv`

---

**4. Run the Agent**

`python agent.py --target icici`

- Expected output: "✅ Match / Green ✅"

---
**5. Validate Output** *(Optional)*

- `python scripts/check_out.py`

- Expected output: "Exact match: True"

---


## ⚙️ How It Works

### 1.  Autonomous Code Generation
- **Input**: Sample PDF + expected CSV schema
- **Process**: LLM generates complete parser with error handling
- **Validation**: Strict `DataFrame.equals()` comparison
- **Self-Correction**: Automatic fixes for common issues:
  - Date format conversion (YYYY-MM-DD → DD-MM-YYYY)
  - Numeric normalization (remove commas, handle parentheses)
  - Header artifact cleanup (OCR noise, duplicate headers)

### 2. Generated Parser Contract

`def parse(pdf_path: str) -> pd.DataFrame:
"""`
Parse bank statement PDF into standardized DataFrame.


- Returns:
    DataFrame with columns: [Date, Description, Debit Amt, Credit Amt, Balance]
    - Dates: DD-MM-YYYY string format
    - Amounts: Float64 with proper null handling
    - Schema: Exact match to reference CSV
"""

---
## 📁 Project Structure
```
ai-agent-challenge/
├── agent.py                 # Main LangGraph agent implementation
├── custom_parsers/          # Generated parser modules
│ ├── init.py                # Package initialization
│ └── icici_parser.py        # Generated ICICI parser (with CLI)
├── data/                    # Sample bank statement data
│ └── icici/
│ ├── icici_sample.pdf       # Input PDF statement
│ └── icici_sample.csv       # Expected DataFrame output
├── scripts/
│ └── check_out.py           # Output validation utility
├── utils/                   # Helper utilities
├── tests/                   # Test suite
├── .env.example             # Environment template
├── .gitignore               # Git ignore rules
└── requirements.txt         # Python dependencies

```
---
## 🔧 Configuration

Environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | Primary LLM provider |
| `GROQ_API_KEY` | *required* | Groq API authentication |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model selection |
| `GEMINI_API_KEY` | *optional* | Fallback provider |
| `AGENT_MAX_TRIES` | `6` | Maximum retry attempts |
| `AGENT_TIMEOUT` | `60` | Execution timeout (seconds) |
---
## 🧪 Testing & Validation

### Built-in Validation
- **Exact Equality**: `DataFrame.equals()` ensures perfect matches
- **Schema Compliance**: Column order, types, and formats verified
- **Edge Case Handling**: Empty rows, header artifacts, numeric edge cases

### Manual Verification
- Quick validation script

`python scripts/check_out.py`


- Output includes:

    - Shape: (100, 5)
    - Columns: ['Date', 'Description', 'Debit Amt', 'Credit Amt', 'Balance']
    - Date samples: ['01-08-2024', '02-08-2024', '03-08-2024']
    - All DD-MM-YYYY: True
    - Exact match: True


### Generated Parser CLI
- Each parser includes a standalone CLI:
- python custom_parsers/icici_parser.py input.pdf output.csv
---


## 🏦 Adding New Banks

The agent is designed for **zero-configuration** bank addition:

**1. Create data structure**:
```
mkdir -p data/<bank_name>

- Add your files:

data/<bank_name>/<bank_name>_sample.pdf

data/<bank_name>/<bank_name>_sample.csv
```

**2. Run agent**:

`python agent.py --target <bank_name>`


**3. Agent automatically**:
- Analyzes PDF structure and CSV schema
- Generates bank-specific parsing logic
- Validates against sample data
- Self-corrects until exact match

## 🎯 Challenge Compliance

- This implementation addresses all evaluation criteria:

### Agent Autonomy (35%)
- ✅ Self-debugging loops with targeted feedback
- ✅ Automatic issue detection and correction
- ✅ Zero manual intervention after configuration

### Code Quality (25%)
- ✅ Clean LangGraph architecture with typed nodes
- ✅ Comprehensive error handling and logging
- ✅ Professional documentation and comments

### Architecture (20%)
- ✅ Clear state machine design with isolated concerns
- ✅ Modular validator with extensible heuristics
- ✅ Robust parser generation and testing pipeline

### Demo Ready (20%)
- ✅ Complete ≤60s demo flow
- ✅ Fresh clone → configuration → success
- ✅ Clear success indicators and validation
---
## 🔑 API Providers

### Primary: Groq (Recommended)
- Get your free API key at: https://groq.com

      Model: Llama-3.3-70B-Versatile

- Benefits: Fast inference, reliable code generation, generous free tier


### Fallback: Google Gemini
- Get your API key at: https://makersuite.google.com/app/apikey
  
  - Configure in `.env: GEMINI_API_KEY=your_key_here`

---

## 🐛 Troubleshooting

### Common Issues

1. **API Key Missing**
  ```
  Error: GROQ_API_KEY not found in environment
  ```
  **Solution:**  Ensure .env file exists and contains: `echo "GROQ_API_KEY=your_key_here" >> .env`

2. **PDF Processing Errors**
```
Error: Could not extract text from PDF
```
**Solution:** Verify PDF is text-based (not scanned image)


3. **DataFrame Mismatch**
```
Info: Date format mismatch detected, retrying with DD-MM-YYYY conversion
```

**Solution:** Agent automatically handles this via self-correction

### Debug Mode
```
Verbose logging for troubleshooting

python -u agent.py --target icici
```

---
## 🚀 Usage (Demo)

**Complete demo from fresh clone:**
```bash
git clone <https://github.com/Manobhiramlol/ai-agent-challenge.git> && cd ai-agent-challenge

pip install -r requirements.txt

cp .env.example .env

Edit .env to add GROQ_API_KEY/gemini_API_KEY (hidden in demo)

python agent.py --target icici   # → "✅ Match / Green ✅"

python scripts/check_out.py      # → "Exact match: True"
```


## ⚡ Advanced Usage

1. ### Custom Configuration

- **Override default settings**

  - ````export AGENT_MAX_TRIES=3````

  - `export AGENT_TIMEOUT=120`
```python
python agent.py --target icici
```


2. ### Testing Generated Parsers

Run all tests

```python
python -m pytest tests/ -v

````
Test specific parser

```python
python -m pytest tests/test_icici_parser.py -v 

```


3. ### Batch Processing

```bash
# Process multiple banks
for bank in icici sbi hdfc; do
    python agent.py --target $bank
done
```


## 🤝 Contributing

**1. Fork and Clone**

- git fork <https://github.com/apurv-korefi/ai-agent-challenge>

- git clone <https://github.com/Manobhiramlol/ai-agent-challenge.git>
```bash
cd ai-agent-challenge
```


**2. Create Feature Branch**
```bash
git checkout -b feature/bank-xyz
```


**3. Add Bank Sample Data**
```bash
mkdir -p data/xyz

Add xyz_sample.pdf and xyz_sample.csv
```

**4. Test Implementation**
```python
python agent.py --target xyz

python scripts/check_out.py
```


**5. Submit Pull Request**
```bash
git add .
git commit -m "Add XYZ bank parser support"
git push origin feature/bank-xyz
```

## 📄 License

This project is developed for the **Agent-as-Coder Challenge**. See challenge documentation for terms.

## 🙏 Acknowledgments

- **LangGraph**: Agent orchestration framework
- **Groq**: High-performance LLM inference  
- **pdfplumber**: Reliable PDF text extraction
- **Challenge**: Inspired by mini-swe-agent architecture

---

**Challenge Status**: ✅ Complete - Ready for evaluation


