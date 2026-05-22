# Installation

## Commands

Copy-paste install steps: [README Requirements and Quick Start](https://github.com/Ndevu12/Research_Assistant_Model#requirements).

This page covers what gets installed, layout, and verification — not repeated bash blocks from the README.

## What you need

| Requirement | Version / notes |
|-------------|-----------------|
| Python | 3.13+ |
| Pipenv | Dependency and virtualenv management |
| Internet | API retrieval; optional after Ollama model download for local LLM |
| RAM (local LLM) | 4–6 GB (`llama3.2:3b`) or 8–10 GB (`llama3.1:8b`) |

Cloud LLM providers (OpenAI, Anthropic) need only an API key — no Ollama install.

!!! warning "Default quality profile"
    Out of the box, synthesis and query expansion run in **heuristic mode** (`llm_enabled: false`). Reports are fast but use template-driven cross-paper analysis rather than LLM-authored synthesis. Enable `RA_SYNTHESIS__LLM_ENABLED=true` and `RA_QUERY_EXPANSION__LLM_ENABLED=true` for higher quality with 8B+ local or cloud models. See [Heuristic vs LLM](../llm/heuristic-vs-llm.md).

## What gets installed

`pipenv install` reads `Pipfile` / `Pipfile.lock` and installs:

| Package category | Examples | Role |
|------------------|----------|------|
| LLM agents | `pydantic-ai` | Structured LLM calls |
| HTTP | `aiohttp` | Scholarly API retrieval |
| Embeddings | `sentence-transformers` | Dedup, ranking, clustering |
| Config | `pydantic`, `pydantic-settings` | Settings and schemas |
| Clustering | `hdbscan` | Thematic paper groups |
| CLI UX | `rich` | Progress streaming |

**Not included by default:** FastAPI and uvicorn (optional API layer). See [API overview](../api/index.md).

## Project layout (install-relevant)

```
Research_Assistant_Model/
├── config/           # YAML defaults (merged at runtime)
├── src/              # Application code (`python -m src`)
├── setups/           # Ollama install, health check, model pull
├── Pipfile           # Dependency manifest
├── .env.example      # Template for local secrets
└── data/             # Created at runtime (embeddings cache, SQLite)
```

`data/`, `logs/`, and `reports/` are gitignored and created on first run.

## Optional `.env` setup

Copy `.env.example` to `.env` before first run if you want persistent overrides:

```bash
cp .env.example .env
```

!!! warning "Debug flag in example file"
    `.env.example` sets `RA_DEBUG=1`. Comment it out unless you want debug JSON dumps in `logs/debug/` on every run.

Key sections in `.env`: LLM provider, retrieval API keys, pipeline flags. Full reference: [Environment variables](../configuration/environment-variables.md).

## Verify installation

Run the health check flow: [Health check](health-check.md) (commands live in [Setup system](../setup-system/index.md#quick-start)).

## Development install

For tests and docs tooling, install dev dependencies per [Local development setup](../development/local-setup.md#initial-setup), then run tests via [Testing](../development/testing.md).

## Next steps

- [Quick start](quick-start.md) — first query and what runs internally
- [Health check](health-check.md) — validate Ollama and models
- [Configuration precedence](../configuration/precedence.md)
