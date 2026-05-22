# Testing

<!-- canonical: pytest -->

pytest suite covering configuration, pipeline stages, retrieval providers, LLM layer, CLI, and extensibility. All tests run offline with mocks — no live LLM or scholarly API calls in CI.

Source: `tests/test_*.py` (28 files). Internal index: [`docs/_analysis/test-behavior-index.md`](https://github.com/Ndevu12/Research_Assistant_Model/blob/main/docs/_analysis/test-behavior-index.md) (repo-only; not published on the docs site).

## Run tests

```bash
pipenv install --dev
pipenv run pytest                    # full suite
pipenv run pytest -v                 # verbose
pipenv run pytest -m "not slow"      # skip subprocess integration tests
pipenv run pytest tests/test_synthesis.py -v   # single file
```

Async tests use `pytest-asyncio` (configured for auto mode on async test functions).

## Test map by domain

| Domain | Files | What they verify |
|--------|-------|------------------|
| Config / LLM resolution | `test_config_settings.py`, `test_resolve_llm_features.py`, `test_model_selection.py` | YAML merge, env overrides, auto LLM flags, Ollama catalog selection |
| Pipeline core | `test_pipeline_core.py`, `test_paper_adapters.py` | Stage ordering, partial failure, disabled stages, metrics |
| Research stages | `test_research_stages.py`, `test_research_quality.py` | Expansion, ranking, relevance, clustering, dedup; multi-domain quality |
| Retrieval | `test_retrieval_stage.py`, `test_providers.py` | Provider failure tolerance, normalization, health checks |
| Synthesis / gaps | `test_synthesis.py` | Heuristic + LLM paths, stage recovery, timeout handling |
| Reporting | `test_reporting.py`, `test_export.py` | Markdown/JSON/HTML, citations, executive summary |
| LLM providers | `test_llm_providers.py`, `test_graceful_response_handling.py` | Provider registry, base URL normalization, JSON retry/fallback utils |
| CLI / interactive | `test_main_mode_detection.py`, `test_interactive_mode.py`, `test_complete_workflow.py`, others | Mode detection, session UX, subprocess flows |
| Memory / filters | `test_memory.py`, `test_interactive_filters.py` | SQLite sessions, follow-up filters |
| Extensibility | `test_phase3_extensibility.py` | Registry bootstrap, stub providers, API scaffold, events |
| Progress | `test_progress_reporter.py` | TTY detection, stage labels |

## Mocking strategy

### LLM calls

All LLM integration tests **mock pydantic-ai** — no Ollama or cloud API required:

| Pattern | Example location |
|---------|------------------|
| `patch create_llm_agent` | `test_synthesis.py` |
| `patch` OpenAI/Pydantic AI constructors | `test_llm_providers.py` |
| `MagicMock(EnhancedResponseHandler)` | synthesis workflow tests |

This keeps CI fast and deterministic. Manual LLM verification uses the CLI with real providers.

### Retrieval providers

| Pattern | Purpose |
|---------|---------|
| `SuccessProvider` / `FailingProvider` / `EmptyProvider` stubs | Stage-level retrieval tests |
| `patch get_enabled_providers` | Control which providers run |
| `AsyncMock` aiohttp sessions | Provider health check tests |
| Normalization unit tests | Raw API payload → `RetrievedPaper` mapping |

### Embeddings

| Fixture | Purpose |
|---------|---------|
| `FixedEmbeddingProvider` | Deterministic vectors for ranking/relevance/quality tests |
| `MockEmbeddingProvider` | Lightweight stub for stage tests |
| `patch.object(provider, "_load_model")` | Skip sentence-transformers model load |

### Pipeline stubs

| Stub | Purpose |
|------|---------|
| `EchoStage`, `FailingStage`, `PartialStage` | Pipeline core behavior |
| `RetrievalStub` | End-to-end stage chain without HTTP |
| `mock_pipeline_result` (`tests/helpers/pipeline_mocks.py`) | Orchestrator output tests |

### CLI / subprocess

| Pattern | Notes |
|---------|-------|
| `patch sys.argv` + `patch asyncio.run` | Unit-test `__main__` without subprocess |
| `@pytest.mark.slow` subprocess tests | `test_complete_workflow.py` — real `python -m src` |
| `capsys` | Assert stdout/stderr formatting |

Skip slow tests in quick loops: `pytest -m "not slow"`.

## Key test behaviors

### LLM feature resolution (`test_resolve_llm_features.py`)

| Test | Confirms |
|------|----------|
| `test_llm_mode_auto_8b` | Ollama 8B + auto → LLM on, `max_llm_papers=5` |
| `test_llm_mode_auto_3b` | Ollama 3B + auto → LLM off |
| `test_cloud_provider_auto_enables_llm` | OpenAI + auto → LLM on |
| `test_env_llm_enabled_overrides_mode` | Env bool beats `llm_mode: off` |

### Multi-domain quality (`test_research_quality.py`)

Parametrized cases across NLP, biomedical, climate, and economics domains:

- No degenerate query variants
- Embedding outlier demotes homonym decoys
- Adaptive relevance filter drops off-topic papers
- Executive summary excludes decoy terms
- No hardcoded ML-specific branch constants in source

### Extensibility (`test_phase3_extensibility.py`)

- Stub providers (PubMed, CORE, DBLP) registered but `NotImplementedError` on search
- `bootstrap_default_plugins()` registers 7 providers + 11 stages
- `StageEventCollector` fires start/complete events
- FastAPI `create_app` requires optional dependency

## Fixtures and helpers

| Path | Role |
|------|------|
| `tests/helpers/pipeline_mocks.py` | `mock_pipeline_result()` for orchestrator tests |
| `catalog_dir` fixture | Temp `ollama_models.yaml` for selection tests |
| `temp_config_dir` fixture | YAML overlay merge tests |
| `memory_store` fixture | Tmp SQLite for session tests |

## Coverage gaps

Document these when adding tests:

| Gap | Detail |
|-----|--------|
| Query understanding | No dedicated unit test file |
| API routes | Scaffold tests only — no HTTP integration tests |
| `EnhancedResponseHandler` | Subcomponents tested; not end-to-end |
| Live LLM / API | All mocked in unit tests |
| Subprocess tests | Marked `@pytest.mark.slow`; may skip in tight CI |

## Writing new tests

1. **Import style**: use absolute imports (`from src.module import ...`) in tests — see [Import conventions](import-conventions.md).
2. **Async stages**: mark with `@pytest.mark.asyncio`.
3. **Avoid live network**: mock aiohttp or patch provider classes.
4. **Deterministic embeddings**: prefer `FixedEmbeddingProvider` over real sentence-transformers loads.
5. **Config isolation**: use `AppSettings(...)` kwargs or `monkeypatch` for env — do not rely on developer `.env`.

Example minimal stage test:

```python
import pytest
from src.config.settings import AppSettings
from src.core.context import PipelineContext
from src.research.query_expansion import QueryExpansionStage

@pytest.mark.asyncio
async def test_expansion_produces_variants() -> None:
    stage = QueryExpansionStage()
    ctx = PipelineContext(settings=AppSettings(), query="machine learning")
    result = await stage.run(ctx, "machine learning")
    assert len(result.output.variants) >= 1
```

## Related pages

- [Local development setup](local-setup.md) — install and run commands
- [Extensibility](extensibility.md) — registry patterns tested in phase3
- [Heuristic vs LLM](../llm/heuristic-vs-llm.md) — behavior under test in synthesis/resolve tests
