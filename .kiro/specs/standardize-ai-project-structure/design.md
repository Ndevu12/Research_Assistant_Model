# Design Document: Standardize AI Project Structure

## Overview

This design document outlines the restructuring of the AI Research Assistant project to follow standard AI project conventions. The current structure has all logic in a single `model.py` file with setup scripts scattered in a `setup/` directory at the root. The new structure will organize code into a proper Python package with clear module boundaries for retrieval, analysis, and utilities.

**Note:** This is a project structure refactoring task that involves organizing files into a proper Python package structure. Property-based testing is NOT appropriate for this feature because:
- It's primarily about file organization and module boundaries
- Most acceptance criteria are about file/directory existence (SMOKE tests)
- There are no universal properties that vary meaningfully with different inputs
- The behavior doesn't change based on input - it's a one-time structural change

Instead, this feature will use:
- **Smoke tests**: Verify file/directory existence
- **Example-based tests**: Verify import compatibility and command execution
- **Integration tests**: Verify the full workflow functions correctly

## Architecture

The new architecture follows a standard Python package structure with clear separation of concerns:

```
project-name/
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
│   └── utils/            # Helper functions and setup scripts
│       ├── __init__.py
│       ├── setup.py      # Python dependency installation
│       ├── ollama.py     # Ollama installation and model setup
│       └── run_setup.py  # Main setup orchestration
├── notebooks/            # Jupyter notebooks
├── tests/                # Unit and integration tests
│   ├── __init__.py
│   ├── conftest.py       # Shared fixtures
│   ├── test_retrieval.py
│   ├── test_analysis.py
│   └── test_integration.py
├── data/                 # Data storage (ignored in git)
├── docs/                 # Documentation
├── Pipfile               # Dependencies
├── Pipfile.lock          # Lock file
├── pyproject.toml        # Build configuration
├── .env                  # Environment variables (ignored in git)
├── .gitignore
└── README.md
```

### Module Boundaries

| Module | Responsibility | Dependencies |
|--------|---------------|--------------|
| `src.retrieval` | Fetch papers from OpenAlex and Semantic Scholar APIs | `aiohttp`, `pydantic` |
| `src.analysis` | LLM-based paper analysis using pydantic-ai | `pydantic-ai`, `src.retrieval` |
| `src.utils` | Helper functions and setup scripts | None (standalone) |
| `src.__main__` | Entry point, orchestrates research workflow | `src.retrieval`, `src.analysis` |

### Import Path Examples

**Within the package (relative imports):**
```python
# In src/retrieval/openalex.py
from ..models import RetrievedPaper
from ..helpers import _normalize_title

# In src/analysis/llm.py
from ..retrieval.models import PaperAnalysis

# In src/__main__.py
from .retrieval.openalex import search_openalex
from .retrieval.semanticscholar import search_semantic_scholar
from .analysis.llm import analysis_agent
```

**From external scripts (absolute imports):**
```python
# In external scripts
from src.retrieval.openalex import search_openalex
from src.retrieval.semanticscholar import search_semantic_scholar
from src.analysis.llm import analysis_agent
from src.utils.run_setup import run_setup
```

## Components and Interfaces

### Entry Point (`src/__main__.py`)

The entry point will be a simple script that:
1. Parses command-line arguments (query and optional flags)
2. Runs the research workflow
3. Supports `--help` for usage information

```python
# src/__main__.py
import argparse
import asyncio
import sys

from .retrieval.openalex import search_openalex
from .retrieval.semanticscholar import search_semantic_scholar
from .retrieval.helpers import _dedupe
from .retrieval.rendering import render_markdown
from .analysis.llm import analysis_agent


async def run_research_helper(user_text: str, k_each: int = 8) -> None:
    # ... existing orchestrator logic ...
    pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Research Assistant - Retrieve and analyze academic papers"
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="On-device LLM reasoning for IoT DDoS detection",
        help="Research query (default: On-device LLM reasoning for IoT DDoS detection)"
    )
    args = parser.parse_args()
    
    asyncio.run(run_research_helper(args.query))


if __name__ == "__main__":
    main()
```

### Module Interfaces

**`src.retrieval` module:**
- `search_openalex(session, query, per_page)` - Search OpenAlex API
- `search_semantic_scholar(session, query, limit)` - Search Semantic Scholar API
- `RetrievedPaper` - Data class for retrieved papers
- `render_markdown(report)` - Render research report as markdown

**`src.analysis` module:**
- `analysis_agent` - Pydantic AI agent for paper analysis
- `PaperAnalysis` - Data model for paper analysis
- `ResearchReport` - Data model for research report

**`src.utils` module:**
- `install_python_deps()` - Install Python dependencies via pipenv
- `install_ollama()` - Install Ollama (OS-aware)
- `setup_ollama_model(model_name)` - Setup Ollama model
- `run_setup()` - Run all setup steps

## Data Models

### `RetrievedPaper` (src/retrieval/models.py)

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class RetrievedPaper:
    title: str
    abstract: Optional[str]
    year: Optional[int]
    venue: Optional[str]
    url: Optional[str]
    doi: Optional[str]
    source: str  # "openalex" or "semanticscholar"
```

### `PaperAnalysis` (src/analysis/llm.py)

```python
from pydantic import BaseModel, Field
from typing import List, Optional


class PaperAnalysis(BaseModel):
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    doi: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)
    why_relevant: List[str] = Field(default_factory=list)
```

### `ResearchReport` (src/analysis/llm.py)

```python
from pydantic import BaseModel
from typing import List


class ResearchReport(BaseModel):
    query: str
    papers: List[PaperAnalysis]
```

## Correctness Properties

*This feature does not include correctness properties because it is a project structure refactoring task. Property-based testing is not appropriate for file organization and module boundary definitions.*

## Error Handling

### Migration Error Handling

1. **File conflicts**: If files already exist in the new structure, the migration script should:
   - Check for conflicts before moving files
   - Prompt user for confirmation to overwrite
   - Create backups of existing files if requested

2. **Import errors**: After migration:
   - Verify all imports work correctly
   - Test the entry point with `python -m src --help`
   - Run a simple test query to verify functionality

3. **Setup script errors**: If setup scripts fail:
   - Provide clear error messages indicating which step failed
   - Suggest manual installation steps
   - Log errors to a file for debugging

### Runtime Error Handling

1. **API errors**: Handle rate limits and connection errors with retries
2. **Model errors**: Handle Ollama connection errors gracefully
3. **Parsing errors**: Handle LLM output parsing errors with fallback messages

## Testing Strategy

### Dual Testing Approach

- **Smoke tests**: Verify file/directory existence and basic setup
- **Example-based tests**: Verify specific behaviors and import compatibility
- **Integration tests**: Verify the full workflow functions correctly

### Test Organization

```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── test_retrieval.py     # Unit tests for retrieval functions
├── test_analysis.py      # Unit tests for analysis functions
└── test_integration.py   # Integration tests for full workflow
```

### Test Coverage

**Smoke Tests:**
- Verify `src/` directory exists
- Verify `src/__init__.py` exists
- Verify `src/__main__.py` exists
- Verify `src/retrieval/` directory and files exist
- Verify `src/analysis/` directory and files exist
- Verify `src/utils/` directory and files exist
- Verify `notebooks/` directory exists
- Verify `tests/` directory exists
- Verify `data/` directory exists
- Verify `docs/` directory exists
- Verify `.env` exists
- Verify `pyproject.toml` exists

**Example-Based Tests:**
- Verify relative imports work within the package
- Verify absolute imports work from external scripts
- Verify `python -m src --help` displays usage information
- Verify `python -m src "query"` executes successfully
- Verify `python -m src.utils.run_setup` executes successfully
- Verify `run_setup()` function works correctly
- Verify `install_python_deps()` function works correctly
- Verify `install_ollama()` function works correctly
- Verify `setup_ollama_model()` function works correctly

**Integration Tests:**
- Verify full research workflow executes successfully
- Verify paper retrieval from both APIs
- Verify paper deduplication
- Verify LLM analysis
- Verify markdown rendering

### Test Configuration

- Use `pytest` as the test framework
- Configure `pytest` to run with `--cov` for coverage reporting
- Configure `pytest` to run with `--cov-report=html` for HTML coverage reports
- Use `pytest-asyncio` for async tests
- Use `pytest-mock` for mocking external dependencies

## Migration Plan

### Phase 1: Create New Structure

1. Create new directories:
   - `src/`
   - `src/retrieval/`
   - `src/analysis/`
   - `src/utils/`
   - `notebooks/`
   - `tests/`
   - `data/`
   - `docs/`

2. Create `__init__.py` files in all package directories

3. Create `src/__main__.py` entry point

### Phase 2: Migrate Code

1. Move `model.py` content to new structure:
   - Move retrieval functions to `src/retrieval/openalex.py` and `src/retrieval/semanticscholar.py`
   - Move analysis agent configuration to `src/analysis/llm.py`
   - Move data schemas to `src/retrieval/models.py`
   - Move rendering functions to `src/retrieval/rendering.py`
   - Move helper functions to `src/retrieval/helpers.py`
   - Move orchestrator function to `src/retrieval/orchestrator.py`

2. Move setup scripts:
   - Move `setup/install_deps.py` to `src/utils/setup.py`
   - Move `setup/install_ollama.py` to `src/utils/ollama.py`
   - Move `setup/setup_ollama_model.py` to `src/utils/ollama.py`
   - Move `setup/run_setup.py` to `src/utils/run_setup.py`

3. Move notebook:
   - Move `starting_point/AI_Research_Assistant_Model.ipynb` to `notebooks/`

### Phase 3: Update Imports

1. Update all imports to use relative imports within the `src/` package
2. Update all imports to use absolute imports for external scripts
3. Verify all imports work correctly

### Phase 4: Update Configuration

1. Create `.env` file for environment variables
2. Create `pyproject.toml` for build configuration
4. Update `.gitignore` to include new directories

### Phase 5: Update Documentation

1. Update `README.md` to reflect the new structure
2. Document the new import paths
3. Document how to run the assistant with the new structure

### Phase 6: Add Tests

1. Add smoke tests for file/directory existence
2. Add example-based tests for import compatibility
3. Add integration tests for the full workflow

### Phase 7: Cleanup

1. Delete old `model.py`
2. Delete old `setup/` directory
3. Delete old `starting_point/` directory
4. Verify everything still works correctly

## Configuration Changes

### New Files

1. **`src/__init__.py`**: Empty file to make `src` a Python package
2. **`src/__main__.py`**: Entry point for `python -m src`
3. **`.env`**: Environment variables (ignored in git)
4. **`pyproject.toml`**: Build configuration
6. **`tests/conftest.py`**: Shared fixtures for tests

### Updated Files

1. **`.gitignore`**: Add `data/`, `.env`, `__pycache__/`, `.pytest_cache/`
2. **`README.md`**: Update to reflect new structure

### Deleted Files

1. **`model.py`**: Content migrated to new structure
2. **`setup/` directory**: Content migrated to `src/utils/`
3. **`starting_point/` directory**: Content migrated to `notebooks/`

## User Review

This design document outlines the restructuring of the AI Research Assistant project to follow standard AI project conventions. The new structure organizes code into a proper Python package with clear module boundaries for retrieval, analysis, and utilities.

**Please review the following:**

1. **Directory structure**: Does the new structure meet your requirements?
2. **Module boundaries**: Are the module responsibilities clearly defined?
3. **Import paths**: Are the import path examples clear and correct?
4. **Entry point**: Does the entry point implementation meet your requirements?
5. **Migration plan**: Is the migration plan clear and complete?

**If you have feedback or requests for changes, please let me know. Otherwise, I can proceed with implementing the design.**