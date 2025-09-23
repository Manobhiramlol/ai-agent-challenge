# Agent-as-Coder: Bank PDF Parser Generator

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent-green.svg)](https://langchain-ai.github.io/langgraph/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> An intelligent coding agent that automatically generates custom bank statement PDF parsers through self-correcting loops.

## 🎯 Overview

This project implements an autonomous coding agent that generates bank-specific PDF parser modules. Given a target bank and sample data, the agent writes, tests, and iteratively refines Python code until the output exactly matches the expected CSV format using DataFrame.equals() validation.

### Agent Architecture

The agent operates as a LangGraph state machine with four core phases: **init** (seeds attempt counter), **generate** (LLM writes custom_parsers/<bank>_parser.py), **execute** (runs parser on sample PDF and compares output to reference CSV), and **retry** (analyzes mismatches for date formats, numeric normalization, header artifacts, then provides targeted feedback for the next iteration). The loop terminates on exact DataFrame equality or when the attempt budget is exhausted, ensuring robust autonomous operation without manual intervention.

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- Groq API key (free tier available at [groq.com](https://groq.com))

### Installation

1. **Clone the repository**
git clone https://github.com/yourusername/ai-agent-challenge.git
cd ai-agent-challenge

2. **Install dependencies**
pip install -r requirements.txt

3. **Configure environment**
cp .env.example .env

Edit .env and add your API keys:
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=groq
GROQ_MODEL=llama-3.3-70b-versatile

4. **Run the agent**
python agent.py --target icici

*Expected output: "✅ Match / Green ✅"*

5. **Validate results** *(Optional)*
python scripts/check_out.py


*Confirms "Exact match: True" and displays DataFrame statistics*

## 📋 Features

- **Autonomous Code Generation**: Writes complete parser modules with minimal human input
- **Self-Correcting Loops**: Automatically detects and fixes common parsing issues
- **Robust Validation**: Uses DataFrame.equals() for exact CSV matching
- **Multiple LLM Support**: Groq (default) and Google Gemini providers
- **Extensible Design**: Easy to add new banks by providing PDF/CSV samples

## 🏗️ Generated Parser Contract

Each generated parser follows this interface:

def parse(pdf_path: str) -> pd.DataFrame:
"""
Extracts bank statement data from PDF.


Returns:
    DataFrame with columns: [Date, Description, Debit Amt, Credit Amt, Balance]
    - Dates formatted as DD-MM-YYYY strings
    - Numeric columns properly coerced with comma/parentheses handling
"""


## 📁 Project Structure

ai-agent-challenge/
├── agent.py # Main agent implementation
├── custom_parsers/ # Generated parser modules
│ └── icici_parser.py # Example generated parser
├── data/ # Sample bank data
│ └── icici/
│ ├── icici_sample.pdf # Input PDF
│ └── icici_sample.csv # Expected output
├── scripts/
│ └── check_out.py # Output validation utility
└── .env.example # Environment configuration template


## 🔧 Configuration

Key environment variables in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `groq` | LLM provider (groq/gemini) |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `AGENT_MAX_TRIES` | `6` | Maximum retry attempts |
| `AGENT_TIMEOUT` | `60` | Execution timeout (seconds) |

## 🧪 Adding New Banks

To extend the agent for a new bank:

1. Create data structure:
data/
└── <bank_name>/
├── <bank_name>_sample.pdf
└── <bank_name>_sample.csv



2. Run the agent:
python agent.py --target <bank_name>


The agent will automatically generate `custom_parsers/<bank_name>_parser.py` and validate against the provided CSV.

## 📊 Evaluation Criteria

This project addresses the challenge requirements:

- **Agent Autonomy (35%)**: Self-debugging loops with targeted feedback
- **Code Quality (25%)**: Clean architecture, type hints, comprehensive documentation
- **Architecture (20%)**: Clear LangGraph node design with isolated concerns
- **Demo Ready (20%)**: Complete ≤60s demo from fresh clone to success

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on [LangGraph](https://langchain-ai.github.io/langgraph/) for agent orchestration
- Uses [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF text extraction
- Free API credits available from [Groq](https://groq.com) and [Google AI](https://ai.google.dev)

---

*Challenge submission for "Agent-as-Coder" - automated coding agent development*