# AI Research Assistant Model

A local AI research assistant that automatically retrieves academic papers from OpenAlex and Semantic Scholar, then analyzes them using Llama 3.2 via Ollama.

## Features

- **Local-first**: Runs entirely on your machine using Ollama + Llama 3.2:3b
- **Dual-source retrieval**: Searches both OpenAlex and Semantic Scholar APIs
- **Deduplication**: Removes duplicate papers based on DOI and normalized title
- **Structured output**: Returns research reports in a consistent JSON schema
- **Auto-setup**: Installs dependencies and configures Ollama automatically

## Requirements

- Python 3.13+
- ~4GB RAM for the 3B model
- Internet connection (for initial setup and API calls)

## Project Structure

```
Research_Assistant_Model/
├── model.py              # Main entry point (auto-setup + execution)
├── requirements.txt      # Python dependencies
├── setup/
│   ├── install_deps.sh   # Install Python dependencies
│   ├── install_ollama.sh # Install Ollama (OS-aware)
│   ├── setup.sh          # Full setup script (non-conda)
│   └── setup_conda.sh    # Full setup script (conda)
├── .kiro/
│   └── settings/
│       └── mcp.json      # MCP server configuration
└── README.md
```

## Installation

### Option 1: Auto-setup (Recommended)

Simply run the main script - it will handle everything:

```bash
python model.py
```

This will:
1. Check/install Python dependencies
2. Check/install Ollama (Arch/Ubuntu/macOS supported)
3. Start Ollama server if needed
4. Pull the `llama3.2:3b` model if needed

**Note:** The first run will install Ollama and download the model (~2GB). This may take several minutes depending on your internet connection.

### Option 2: Manual Setup with Conda

```bash
# Run the setup script
bash setup/setup_conda.sh

# Activate the environment
conda activate research_assistant

# Run the assistant
python model.py
```

### Option 3: Manual Setup (Non-Conda)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the setup script
bash setup/setup.sh

# Run the assistant
python model.py
```

## Usage

### Quick Start

```bash
python model.py
```

The default query is: `"On-device LLM reasoning for IoT DDoS detection"`

### Custom Query

Edit the `QUERY` variable in `model.py`:

```python
if __name__ == "__main__":
    QUERY = "Your research query here"
    asyncio.run(run_research_helper(QUERY))
```

### As a Module

```python
from model import run_research_helper
import asyncio

async def main():
    await run_research_helper("On-device LLM reasoning for IoT DDoS detection")

asyncio.run(main())
```

## Output Format

The assistant returns a markdown-formatted report with:
- Paper title, year, and venue
- Source URL or DOI
- Key points extracted by the LLM
- Relevance explanation for each paper

Example:
```
# Research helper results
Query: On-device LLM reasoning for IoT DDoS detection

## 1. Paper Title
2024 | IEEE IoT Journal
Source: https://doi.org/10.xxxx/xxxxx

Key points:
- Lightweight model architecture
- Edge-based detection
- Low latency inference

Why this matches your query:
- Addresses on-device LLM for IoT
- Focuses on DDoS detection
- Published in relevant venue
```

## Troubleshooting

### Ollama not found
Install Ollama manually:
- Arch Linux: `yay -S ollama` or `sudo pacman -S ollama`
- Ubuntu/Debian: `curl -fsSL https://ollama.com/install.sh | sh`
- macOS: `brew install ollama`
- Windows: Download from https://ollama.com/download

### Model not available
Pull the model manually:
```bash
ollama pull llama3.2:3b
```

### Ollama server not running
Start the server:
```bash
ollama serve
```

### Connection errors
- Check your internet connection
- Verify Ollama is running: `ollama list`
- Ensure the model is pulled: `ollama pull llama3.2:3b`

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   User Query    │────>│  Paper Retrieval │────>│   LLM Analysis  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                              │                        │
                              ▼                        ▼
                    ┌──────────────────┐     ┌─────────────────┐
                    │  OpenAlex API    │     │  Llama 3.2:3b   │
                    │ Semantic Scholar │     │   (via Ollama)  │
                    └──────────────────┘     └─────────────────┘
```

## License

MIT