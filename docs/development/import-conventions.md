# Import Conventions

The codebase uses **relative imports inside `src/`** and **absolute `src.*` imports from tests and external scripts**. The `setups/` package sits beside `src/` and uses absolute imports into `src`.

## Rules

| Context | Import style | Example |
|---------|--------------|---------|
| Inside `src/` package | Relative (`from .` / `from ..`) | `from ..models import AgentFactory` |
| Tests (`tests/`) | Absolute `src.*` | `from src.config.settings import AppSettings` |
| External scripts / REPL | Absolute `src.*` | `from src.retrieval.orchestrator import build_pipeline` |
| `setups/` modules | Absolute `src.*` | `from src.config.model_selection import resolve_target_model` |
| Type-checking only | `TYPE_CHECKING` guard | Avoid circular imports at runtime |

## Inside the package

Modules under `src/` import siblings and parents with relative paths:

```python
# src/retrieval/providers/openalex.py
from ..models import RetrievedPaper

# src/analysis/synthesis.py
from ..models import AgentFactory, AgentRole
from ..retrieval.models import RankedPaper, SynthesisResult
from ..core.context import PipelineContext, StageResult
```

**Depth guide:**

| From | To | Prefix |
|------|-----|--------|
| `src/retrieval/providers/foo.py` | `src/retrieval/models.py` | `from ..models` |
| `src/analysis/synthesis.py` | `src/models/` | `from ..models` |
| `src/core/pipeline.py` | `src/config/settings.py` | `from ..config.settings` |

Prefer relative imports in new `src/` code to keep packages relocatable.

## Lazy imports

Some modules defer imports to break cycles or avoid heavy optional deps:

```python
# src/models/factory.py — defers model_selection import
def _resolve_config(config):
    from ..config.model_selection import resolve_llm_model_name
    ...

# src/api/app.py — FastAPI only when create_app() runs
def create_app(...):
    from fastapi import FastAPI
    ...
```

Follow this pattern when adding optional dependencies — do not import FastAPI at module top level in core pipeline code.

## TYPE_CHECKING blocks

Use for type hints that would create circular imports:

```python
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.settings import LLMConfig
```

Runtime code uses string annotations or deferred imports inside functions.

## Tests

All test files use absolute imports from the repo root:

```python
from src.config.settings import AppSettings
from src.core.pipeline import ResearchPipeline
from src.research.query_expansion import expand_query_heuristic
```

Run pytest from the **repository root** so `src` resolves. Commands: [Testing](testing.md).

Do not use relative imports in `tests/`.

## External scripts and notebooks

```python
from src.retrieval.orchestrator import run_research_helper, build_pipeline
from src.models import AgentFactory, create_llm_provider
from src.config.settings import AppSettings, get_settings

from setups import run_setup, print_report
```

Ensure the project root is on `PYTHONPATH` (Pipenv shell handles this automatically).

## Setups package

`setups/` is not under `src/` but imports from it:

```python
# setups/ollama.py
from src.config.model_selection import resolve_target_model
from src.utils.logging_system import logger
```

Some setup scripts add the parent directory to `sys.path` for CLI invocation — prefer `pipenv run python -m setups.ollama` over ad-hoc path hacks.

## Package entry points

| Entry | Module |
|-------|--------|
| CLI | `python -m src` → `src/__main__.py` |
| API | `uvicorn src.api.app:create_app --factory` |
| Setup | `python -m setups.manager` |

## Anti-patterns

| Avoid | Why |
|-------|-----|
| `from src.foo import bar` inside `src/` | Breaks package-relative layout convention |
| Inline imports in hot paths | Reserved for cycle breaking and optional deps only |
| Importing test helpers from `src/` | Keep test utilities in `tests/helpers/` |

## Related pages

- [Local development setup](local-setup.md) — run commands and IDE setup
- [Extensibility](extensibility.md) — where to register plugins
- [Architecture overview](../architecture/overview.md) — module boundaries
