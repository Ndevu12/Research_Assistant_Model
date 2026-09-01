# Local Development Setup

Development environment for AI Research Assistant: Python 3.11+, Pipenv, pytest, and optional docs tooling.

Source: `Pipfile`, `README.md`, `src/__main__.py`.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.11+ | Floor declared in `Pipfile` `[requires]` (`>=3.11`) |
| Pipenv | Virtualenv and lockfile management |
| Git | Clone the repository |

For LLM development with Ollama, run [Setup system — Quick start](../setup-system/index.md#quick-start). Cloud-only development needs API keys only.

## Initial setup

```bash
git clone https://github.com/Ndevu12/Research_Assistant_Model.git
cd Research_Assistant_Model
pip install pipenv     # externally-managed distro (Arch, Debian 12+, Fedora 39+)? use: pipx install pipenv
pipenv install --dev
cp -n .env.example .env   # optional; -n leaves an existing .env untouched
```

`pipenv install --dev` installs:

- **Runtime packages** (`[packages]`): pydantic-ai, aiohttp, sentence-transformers, hdbscan, etc.
- **Dev packages** (`[dev-packages]`): mkdocs, mkdocs-material, mkdocs-mermaid2-plugin

Optional API development:

```bash
pipenv install fastapi uvicorn
```

## Run the application

Always use Pipenv so dependencies resolve correctly. Copy-paste invocations: [CLI reference](../user-guide/cli.md) and [README Usage](https://github.com/Ndevu12/Research_Assistant_Model#usage).

!!! warning "Plain python may miss deps"
    Running `python -m src` outside the Pipenv shell can fail on imports like `sentence-transformers`. Use `pipenv run` or `pipenv shell` first.

## Shell workflow

```bash
pipenv shell
python -m src "your query"
```

From the shell, run `pytest` and `mkdocs serve` per [Testing](testing.md) and [Publishing docs](publishing.md).

Exit the shell with `exit` or Ctrl+D.

## Configuration for development

| Task | Approach |
|------|----------|
| Persistent local overrides | Edit `.env` (see [Environment variables](../configuration/environment-variables.md)) |
| YAML experiments | Add overlay files under `config/` or set `RA_CONFIG_DIR` |
| Debug pipeline dumps | `RA_PIPELINE__DEBUG=true` or `RA_DEBUG=1` → `logs/debug/` |
| Fast iteration (heuristic) | Default 3B Ollama or `RA_SYNTHESIS__LLM_ENABLED=false` |
| LLM integration testing | Pin `llama3.1:8b` or use cloud keys — all unit tests mock LLM by default |

Comment out `RA_DEBUG=1` in `.env.example` unless you want debug JSON on every run.

## Project layout (development)

```
Research_Assistant_Model/
├── src/                 # Application package (python -m src)
│   ├── __main__.py      # CLI entry
│   ├── api/             # Optional FastAPI layer
│   ├── config/          # Settings, LLM resolution
│   ├── core/            # Pipeline, registry, context
│   ├── research/        # Query expansion, ranking, clustering
│   ├── retrieval/       # Providers, retrieval stage
│   ├── analysis/        # Synthesis, gap analysis
│   └── reporting/       # Report generation, exports
├── tests/               # pytest suite
├── config/              # YAML defaults
├── setups/              # Ollama install, health check
├── docs/                # MkDocs source
└── logs/                # Runtime logs (gitignored)
```

## Common development tasks

| Task | Command / link |
|------|----------------|
| Run all tests | [Testing](testing.md) |
| Skip slow subprocess tests | [Testing — Run tests](testing.md#run-tests) |
| Single test file | [Testing — Run tests](testing.md#run-tests) |
| Docs preview | [Publishing docs](publishing.md) |
| Strict docs build | [Publishing docs](publishing.md) |
| Health check | [Setup system](../setup-system/index.md#quick-start) |
| API server | [API overview](../api/index.md#install-and-run) |

## IDE / editor notes

- Set the Python interpreter to the Pipenv virtualenv: `pipenv --venv`
- Mark `src/` as sources root if your IDE supports it
- Tests import via `from src....` — run pytest from repo root

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `ModuleNotFoundError: sentence_transformers` | `pipenv install` inside project root |
| Ollama connection errors | [Setup system](../setup-system/index.md#quick-start) |
| Tests hang on subprocess | Use `pytest -m "not slow"` |
| MkDocs strict warnings | Fix broken nav links; run `mkdocs build --strict` locally |

## Related pages

- [Testing](testing.md) — test map and mocking strategy
- [Import conventions](import-conventions.md) — relative vs absolute imports
- [Installation](../getting-started/installation.md) — end-user install guide
- [Publishing docs](publishing.md) — GitHub Pages deploy
