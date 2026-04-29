# AI Research Assistant

A local-first AI research assistant that automatically retrieves academic papers from OpenAlex and Semantic Scholar, then analyzes them using Llama 3.2 via Ollama. Built with Python 3.13, pydantic-ai, and async/await for efficient paper retrieval and analysis.

## Features

- **Local-first**: Runs entirely on your machine using Ollama + Llama 3.2:3b
- **Dual-source retrieval**: Searches both OpenAlex and Semantic Scholar APIs in parallel
- **Smart deduplication**: Removes duplicate papers based on DOI and normalized title matching
- **Structured output**: Returns research reports in a consistent JSON schema using Pydantic models
- **Auto-setup**: Automatically installs dependencies and configures Ollama
- **Async architecture**: Fast concurrent API calls using aiohttp
- **Modular design**: Clean separation of retrieval, analysis, and utility modules

## Requirements

- Python 3.13+
- ~4GB RAM for the Llama 3.2:3b model
- Internet connection (for initial setup and API calls)
- Pipenv for dependency management

## Project Structure

```
Research_Assistant_Model/
├── src/                  # Source code package
│   ├── __init__.py       # Package initialization
│   ├── __main__.py       # Entry point (enables `python -m src`)
│   ├── retrieval/        # Paper retrieval logic
│   │   ├── __init__.py
│   │   ├── openalex.py   # OpenAlex API client
│   │   ├── semanticscholar.py  # Semantic Scholar API client
│   │   ├── models.py     # Data schemas (PaperAnalysis, ResearchReport, RetrievedPaper)
│   │   ├── rendering.py  # Output formatting functions
│   │   ├── helpers.py    # Helper functions (_normalize_title, _dedupe, etc.)
│   │   └── orchestrator.py  # Main research workflow orchestration
│   ├── analysis/         # LLM analysis logic
│   │   ├── __init__.py
│   │   └── llm.py        # LLM agent configuration and analysis logic
│   └── utils/            # Utility modules and logging
│       ├── __init__.py
│       ├── logging_system.py    # Structured logging
│       ├── message_formatter.py # Output formatting
│       ├── response_models.py   # Data models
│       └── ... (other utilities)
├── setups/               # Setup and configuration scripts
│   ├── __init__.py       # Package exports
│   ├── setup.py          # Python dependency installation
│   ├── ollama.py         # Ollama installation and model setup
│   ├── manager.py        # Main setup orchestrator
│   ├── health_check.py   # Setup validation
│   └── README.md         # Setup documentation
├── notebooks/            # Jupyter notebooks
├── tests/                # Unit and integration tests
├── data/                 # Data storage (ignored in git)
├── docs/                 # Documentation
├── Pipfile               # Pipenv dependencies
├── Pipfile.lock          # Pipenv lock file (generated)
├── pyproject.toml        # Build configuration
├── .env                  # Environment variables (ignored in git)
├── .gitignore
└── README.md
```

## Installation

### Quick Start (Recommended - Fully Automatic)

```bash
# Install pipenv if not already installed
pip install pipenv

# Install Python dependencies
pipenv install

# Run the assistant (auto-setup runs automatically on first execution)
pipenv run python -m src
```

The first run will automatically:
1. ✅ Check if Ollama is installed
2. ✅ Install Ollama if needed (Arch/Ubuntu/macOS supported)
3. ✅ Start Ollama server if not running
4. ✅ Pull the `llama3.2:3b` model (~2GB download)
5. ✅ Start the research assistant

**Note:** Initial setup may take several minutes depending on your internet connection and system performance.

### Manual Setup (Optional)

If you prefer to set up components manually or troubleshoot:

```bash
# Check setup status
python -m setups.health_check

# Run setup explicitly
python -m setups.manager

# Run setup with custom model
python -m setups.manager --model mistral
```

## Usage

### Command Line

Run with default query:
```bash
pipenv run python -m src
```

Run with custom query:
```bash
pipenv run python -m src "Your research query here"
```

Show help:
```bash
pipenv run python -m src --help
```

### As a Python Module

```python
from src.retrieval.orchestrator import run_research_helper
import asyncio

async def main():
    await run_research_helper("On-device LLM reasoning for IoT DDoS detection")

asyncio.run(main())
```

### Environment Variables

Create a `.env` file (optional):
```bash
# Semantic Scholar API key (optional, increases rate limits)
S2_API_KEY=your_api_key_here
```

## Output Format

The assistant returns a markdown-formatted research report with:
- Query summary
- Top 10 relevant papers (deduplicated)
- For each paper:
  - Title, year, and venue
  - Source URL or DOI
  - Key points extracted by the LLM
  - Relevance explanation

Example output:
```markdown
# Research helper results
Query: On-device LLM reasoning for IoT DDoS detection

## 1. Lightweight LLM Architecture for Edge Devices
2024 | IEEE IoT Journal
Source: https://doi.org/10.xxxx/xxxxx

Key points:
- Novel quantization technique reduces model size by 75%
- Edge-based inference with <100ms latency
- Achieves 95% accuracy on DDoS detection benchmarks

Why this matches your query:
- Directly addresses on-device LLM deployment
- Focuses on IoT security and DDoS detection
- Published in top-tier IoT venue
```

## Troubleshooting

### Setup fails on first run
The automatic setup handles most cases, but if it fails:

```bash
# Check setup status
python -m setups.health_check

# Run setup manually
python -m setups.manager

# Run setup with verbose logging
python -m setups.manager --model llama3.2:3b
```

### Ollama not found
If automatic setup fails to install Ollama, install it manually:
- Arch Linux: `yay -S ollama` or `sudo pacman -S ollama`
- Ubuntu/Debian: `curl -fsSL https://ollama.com/install.sh | sh`
- macOS: `brew install ollama`
- Windows: Download from https://ollama.com/download

Then run setup again:
```bash
python -m setups.manager
```

### Model not available
If the model fails to pull during setup:
```bash
# Pull manually
ollama pull llama3.2:3b

# Or run setup again
python -m setups.manager
```

### Ollama server not running
The automatic setup starts the server, but if it stops:
```bash
# Start manually
ollama serve

# Or run setup again
python -m setups.manager
```

### Connection errors
- Check your internet connection
- Verify Ollama is running: `ollama list`
- Check logs: `tail -f logs/combined_*.log`

### Pipenv issues
If pipenv is not found, install it first:
```bash
pip install pipenv
```

To activate the virtual environment manually:
```bash
pipenv shell
```

### Import errors
If you encounter import errors:
- Ensure you're using `pipenv run` to run commands
- Verify the new structure is in place: `ls src/`
- Run setup again: `python -m setups.manager`

## Architecture

The assistant follows a modular pipeline architecture:

```
┌─────────────────┐
│   User Query    │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Parallel Paper Retrieval       │
│  ┌──────────┐  ┌──────────────┐ │
│  │ OpenAlex │  │   Semantic   │ │
│  │   API    │  │  Scholar API │ │
│  └──────────┘  └──────────────┘ │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Deduplication & Ranking        │
│  (DOI + Title Normalization)    │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  LLM Analysis                   │
│  (Llama 3.2:3b via Ollama)      │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Markdown Report Generation     │
└─────────────────────────────────┘
```

## Development

### Import Paths

**Within the package (relative imports):**
```python
# In src/retrieval/openalex.py
from .models import RetrievedPaper
from .helpers import _normalize_title

# In src/analysis/llm.py
from ..retrieval.models import PaperAnalysis

# In src/__main__.py
from .retrieval.openalex import search_openalex
from .retrieval.semanticscholar import search_semantic_scholar
from .analysis.llm import analysis_agent
```

**From external scripts (absolute imports):**
```python
from src.retrieval.openalex import search_openalex
from src.retrieval.semanticscholar import search_semantic_scholar
from src.analysis.llm import analysis_agent
from setups import run_setup, print_report
```

### Dependencies

Core dependencies (managed via Pipenv):
- `pydantic-ai` - LLM agent framework with structured outputs
- `aiohttp` - Async HTTP client for API calls
- `pydantic` - Data validation and schema definition

### Running in Development

```bash
# Activate virtual environment
pipenv shell

# Run the assistant
python -m src

# Run setup script
python -m setups.manager

# Exit virtual environment
exit
```

## License

MIT