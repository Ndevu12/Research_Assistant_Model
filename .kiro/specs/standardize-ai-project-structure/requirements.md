# Requirements Document

## Introduction

This feature standardizes the AI Research Assistant project structure to follow standard AI project conventions. The current structure has all logic in a single `model.py` file with setup scripts scattered in a `setup/` directory at the root. The new structure will organize code into a proper Python package with clear module boundaries for retrieval, analysis, and utilities, while maintaining all existing functionality.

## Glossary

- **AI Research Assistant**: The application that retrieves academic papers from OpenAlex and Semantic Scholar APIs and analyzes them using Llama 3.2 via Ollama
- **Package**: A Python package structure with `__init__.py` files and organized modules
- **Retrieval Module**: Code responsible for fetching papers from external APIs (OpenAlex, Semantic Scholar)
- **Analysis Module**: Code responsible for LLM-based analysis of retrieved papers
- **Utils Module**: Helper functions and setup scripts
- **Entry Point**: The main script that orchestrates the research workflow

## Requirements

### Requirement 1: New Directory Structure

**User Story:** As a developer, I want a standardized project structure, so that the codebase follows AI project conventions and is easy to navigate.

#### Acceptance Criteria

1. THE Project SHALL have a `src/` directory containing all source code
2. THE Project SHALL have a `src/__init__.py` file to make it a Python package
3. THE Project SHALL have a `src/__main__.py` file as the new entry point
4. THE Project SHALL have a `src/retrieval/` directory with `__init__.py`, `openalex.py`, and `semanticscholar.py`
5. THE Project SHALL have a `src/analysis/` directory with `__init__.py` and `llm.py`
6. THE Project SHALL have a `src/utils/` directory with `__init__.py` and `setup.py`
7. THE Project SHALL have a `notebooks/` directory for Jupyter notebooks
8. THE Project SHALL have a `tests/` directory for unit and integration tests
9. THE Project SHALL have a `data/` directory for data storage
10. THE Project SHALL have a `docs/` directory for documentation

### Requirement 2: Module Boundary Definition

**User Story:** As a developer, I want clearly defined module boundaries, so that each component has a single responsibility and dependencies are explicit.

#### Acceptance Criteria

1. THE Retrieval Module SHALL contain all code for fetching papers from OpenAlex and Semantic Scholar APIs
2. THE Analysis Module SHALL contain all code for LLM-based paper analysis using pydantic-ai
3. THE Utils Module SHALL contain helper functions and setup scripts
4. THE Main Module (src/__main__.py) SHALL orchestrate the research workflow by calling retrieval and analysis modules
5. WHEN modules are imported, THE System SHALL NOT have circular dependencies
6. THE Analysis Module SHALL depend on the Retrieval Module for input data
7. THE Main Module SHALL depend on both Retrieval and Analysis modules

### Requirement 3: Code Migration

**User Story:** As a developer, I want existing code moved to the new structure, so that functionality is preserved while improving organization.

#### Acceptance Criteria

1. WHEN `model.py` is migrated, THE System SHALL move paper retrieval functions to `src/retrieval/openalex.py` and `src/retrieval/semanticscholar.py`
2. WHEN `model.py` is migrated, THE System SHALL move analysis agent configuration to `src/analysis/llm.py`
3. WHEN `model.py` is migrated, THE System SHALL move data schemas (`PaperAnalysis`, `ResearchReport`, `RetrievedPaper`) to `src/retrieval/models.py`
4. WHEN `model.py` is migrated, THE System SHALL move rendering functions to `src/retrieval/rendering.py`
5. WHEN `model.py` is migrated, THE System SHALL move helper functions (`_normalize_title`, `_dedupe`, `_openalex_abstract_from_inverted_index`) to `src/retrieval/helpers.py`
6. WHEN `model.py` is migrated, THE System SHALL move the orchestrator function to `src/retrieval/orchestrator.py`
7. WHEN setup scripts are migrated, THE System SHALL move `setup/install_deps.py` to `src/utils/setup.py`
8. WHEN setup scripts are migrated, THE System SHALL move `setup/install_ollama.py` to `src/utils/ollama.py`
9. WHEN setup scripts are migrated, THE System SHALL move `setup/setup_ollama_model.py` to `src/utils/ollama.py`
10. WHEN setup scripts are migrated, THE System SHALL move `setup/run_setup.py` to `src/utils/run_setup.py`
11. WHEN the notebook is moved, THE System SHALL move `starting_point/AI_Research_Assistant_Model.ipynb` to `notebooks/`

### Requirement 4: Import Path Updates

**User Story:** As a developer, I want all import paths updated, so that the code works with the new package structure.

#### Acceptance Criteria

1. WHEN modules are imported, THE System SHALL use relative imports within the `src/` package
2. WHEN external scripts import from the package, THE System SHALL support absolute imports like `from src.retrieval.openalex import search_openalex`
3. WHEN the main entry point runs, THE System SHALL import from the `src/` package
4. WHEN setup scripts run, THE System SHALL import from the `src/utils/` module

### Requirement 5: Entry Point

**User Story:** As a developer, I want a clean entry point, so that the application can be run with standard Python commands.

#### Acceptance Criteria

1. WHEN `python -m src` is executed, THE System SHALL run the research assistant
2. WHEN `python -m src --help` is executed, THE System SHALL display usage information
3. WHEN `python -m src "query"` is executed, THE System SHALL run the research assistant with the specified query
4. THE Entry Point SHALL support both default and custom queries

### Requirement 6: Backward Compatibility

**User Story:** As a developer, I want backward compatibility, so that existing functionality is preserved during the refactoring.

#### Acceptance Criteria

1. WHEN the old `model.py` is deleted, THE System SHALL have equivalent functionality in the new structure
2. WHEN the old `setup/run_setup.py` is deleted, THE System SHALL have equivalent functionality in `src/utils/run_setup.py`
3. WHEN the new structure is in place, THE System SHALL support running `pipenv run python -m src` to execute the assistant
4. WHEN the new structure is in place, THE System SHALL support running `pipenv run python -m src.utils.run_setup` to run setup

### Requirement 7: Configuration

**User Story:** As a developer, I want configuration files in standard locations, so that the project follows Python conventions.

#### Acceptance Criteria

1. THE Project SHALL have a `.env` file for environment variables (ignored in git)
2. THE Project SHALL have a `pyproject.toml` file for build configuration
3. WHEN a `.env` file is created, THE System SHALL include `S2_API_KEY` if available

### Requirement 8: Testing Infrastructure

**User Story:** As a developer, I want testing infrastructure, so that code quality is maintained.

#### Acceptance Criteria

1. WHEN tests are added, THE System SHALL have unit tests for retrieval functions
2. WHEN tests are added, THE System SHALL have unit tests for analysis functions
3. WHEN tests are added, THE System SHALL have integration tests for the full workflow
4. THE Tests Directory SHALL have a `conftest.py` for shared fixtures

### Requirement 9: Documentation

**User Story:** As a developer, I want updated documentation, so that the new structure is understood.

#### Acceptance Criteria

1. WHEN documentation is updated, THE System SHALL update `README.md` to reflect the new structure
2. WHEN documentation is updated, THE System SHALL document the new import paths
3. WHEN documentation is updated, THE System SHALL document how to run the assistant with the new structure

### Requirement 10: Git Ignore

**User Story:** As a developer, I want updated git ignore rules, so that generated files are not committed.

#### Acceptance Criteria

1. WHEN `.gitignore` is updated, THE System SHALL include `data/` directory
2. WHEN `.gitignore` is updated, THE System SHALL include `.env` file
3. WHEN `.gitignore` is updated, THE System SHALL include `__pycache__/` directories
4. WHEN `.gitignore` is updated, THE System SHALL include `.pytest_cache/` directory
