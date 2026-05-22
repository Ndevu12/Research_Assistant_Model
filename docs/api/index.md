# API Overview

The HTTP API is an **optional** FastAPI layer over the full 11-stage research pipeline. It is not installed with the core application.

Source: `src/api/app.py`, `src/api/__init__.py`.

## Install and run

```bash
pipenv install fastapi uvicorn
pipenv run uvicorn src.api.app:create_app --factory --reload
```

The app listens on `http://127.0.0.1:8000` by default. OpenAPI docs: `http://127.0.0.1:8000/docs`.

!!! info "Not in core Pipfile"
    `fastapi` and `uvicorn` are intentionally excluded from `[packages]` in `Pipfile`. Install them when you need the API.

## CLI vs API pipeline

| Aspect | CLI batch (`python -m src "query"`) | API (`POST /research`) |
|--------|-------------------------------------|-------------------------|
| Pipeline builder | `run_research_helper` shortcut | `build_pipeline()` full pipeline |
| Default providers | OpenAlex + Semantic Scholar only | All providers enabled in config |
| Output | stdout / `-o` file | JSON response with `report` + `rendered` |
| Formats | markdown, json, html, pdf | markdown, json, html only |
| Session memory | `--session` flag | Not exposed |

!!! info "Full pipeline on API"
    The API uses `build_pipeline(resolved_settings)` — the same composable pipeline as programmatic use. Enable additional retrieval providers via config. See [CLI vs API](../user-guide/cli-vs-api.md) and [Retrieval overview](../retrieval/overview.md).

## Application factory

`create_app(settings=None)` in `src/api/app.py`:

1. Imports FastAPI (raises `ImportError` with install hint if missing)
2. Calls `bootstrap_default_plugins()` — registers providers and stages
3. Resolves settings via argument or `get_settings()`
4. Mounts `/health`, `/providers`, `/research` routes

Pass custom settings for tests or isolated deployments:

```python
from src.api.app import create_app
from src.config.settings import AppSettings

app = create_app(AppSettings.from_yaml())
```

## Configuration

The API reads the same settings as the CLI:

- YAML in `config/`
- `.env` file
- `RA_*` environment variables

No API-specific config keys exist. Set LLM provider, retrieval toggles, and pipeline flags before starting uvicorn:

```bash
export RA_LLM__PROVIDER=openai
export OPENAI_API_KEY=sk-...
pipenv run uvicorn src.api.app:create_app --factory
```

See [Environment variables](../configuration/environment-variables.md).

## Response shape (summary)

`POST /research` returns:

| Field | Description |
|-------|-------------|
| `query` | Echo of request query |
| `format` | Requested output format |
| `partial` | `true` if any stage failed partially |
| `warnings` | Stage warning messages |
| `duration_ms` | Total pipeline time |
| `session_id` | Pipeline session identifier |
| `metrics` | Stage/retrieval/LLM metrics dict |
| `report` | `EnhancedResearchReport` as JSON |
| `rendered` | Format-specific string (markdown/html) or dict (json) |

Full schemas and examples: [Endpoints](endpoints.md).

## Limitations

| Limitation | Detail |
|------------|--------|
| No `pdf` format | Request `format` pattern allows `markdown\|json\|html` only |
| No streaming | Synchronous await of full pipeline per request |
| No auth | No built-in authentication or rate limiting |
| 500 on pipeline error | Unhandled exceptions become `HTTPException(500)` |
| `export` param | Accepted but behavior depends on `render_report_output` — see endpoints doc |

## Testing

API scaffold tests live in `tests/test_phase3_extensibility.py`. Install FastAPI first (see [Install and run](#install-and-run)), then run:

`pipenv run pytest tests/test_phase3_extensibility.py::TestApiScaffold -v`

Full pytest reference: [Testing](../development/testing.md).

## Related pages

- [Endpoints](endpoints.md) — route reference with JSON examples
- [Architecture overview](../architecture/overview.md) — pipeline stages
- [Local development setup](../development/local-setup.md) — dev environment
