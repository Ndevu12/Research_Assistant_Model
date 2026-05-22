# CLI Reference

<!-- canonical: cli-commands -->

## Commands

This page is the **canonical CLI reference** for flags, execution paths, and examples.

Quick copy-paste invocations: [README Usage](https://github.com/Ndevu12/Research_Assistant_Model#usage).

Entry point: `src/__main__.py` → `main()`.

## Arguments and flags

| Argument / flag | Description |
|-----------------|-------------|
| `query` | Optional positional research query. Omitted → interactive mode. |
| `--format` | Output format: `markdown` (default), `json`, `html`, `pdf` |
| `--export FORMATS` | Comma-separated citations: `bibtex`, `apa`, `mla`, `chicago` |
| `--output`, `-o` | Write report to file (recommended for html/pdf) |
| `--session` | Parsed but **not wired** — use interactive mode for SQLite memory (see [CLI vs API](cli-vs-api.md)) |
| `--no-progress` | Disable live stderr progress |
| `--help` | Show argparse help |

### Examples

```bash
# Markdown to stdout (default)
pipenv run python -m src "graph neural networks survey"

# JSON structured report
pipenv run python -m src --format json "graph neural networks survey"

# Print-ready PDF HTML
pipenv run python -m src --format pdf -o reports/out.pdf.html "query"

# Citations appended after report
pipenv run python -m src --export bibtex,apa,chicago "query"

# Quiet run (CI, scripting)
pipenv run python -m src --no-progress "query"
```

## Execution paths

### Batch mode (`query` provided)

```
main()
  → ensure_setup()           # Ollama setup if needed
  → run_research_helper()    # CLI shortcut path
  → render_report_output()
  → print (or write --output file)
```

!!! info "CLI vs full pipeline"
    Batch mode hardcodes **OpenAlex + Semantic Scholar** in `run_research_helper()`. Provider YAML/env toggles do not add arXiv or CrossRef on this path. Interactive mode uses the full settings merge.

    Full comparison: [CLI vs API](cli-vs-api.md).

### Interactive mode (no `query`)

```
main()
  → ensure_setup()
  → run_interactive_mode()
  → InteractiveResearchSession
  → run_full_query() / handle_follow_up()
```

Uses `run_research_with_result()` with full `AppSettings` — honors all enabled retrieval providers.

See [Interactive sessions](interactive-sessions.md).

## Startup behavior

### Pipenv warning

If `PIPENV_ACTIVE != 1`, a warning is logged recommending `pipenv run python -m src`.

### Ollama auto-setup

When `RA_LLM__PROVIDER=ollama`, `ensure_setup()` runs health checks and may invoke `setups.manager.run_setup()` before the first query. Cloud providers skip this.

## Progress output

Live progress streams to **stderr** (stage bar, LLM previews). Disabled by `--no-progress`, `RA_PIPELINE__STREAM_PROGRESS=false`, or non-TTY stderr.

Report content goes to **stdout** (or `--output` file). Redirect stderr to suppress progress in scripts:

```bash
pipenv run python -m src --no-progress "query" 2>/dev/null
```

See [Progress streaming](../operations/progress-streaming.md).

## Exit behavior

- Setup failure → exit code `1`
- Retrieval exception in helper → error message printed, `None` returned
- Empty results (non-partial) → "no results" message

## Programmatic alternative

For full provider control from Python:

```python
import asyncio
from src.config.settings import AppSettings
from src.retrieval.orchestrator import run_research

async def main():
    settings = AppSettings(
        retrieval={"providers": {"arxiv": {"enabled": True}}}
    )
    report = await run_research("your query", settings=settings)
    print(report.query)

asyncio.run(main())
```

See also: [CLI vs API](cli-vs-api.md), [Output formats](output-formats.md), [Configuration cookbook](configuration-cookbook.md), [Quick start](../getting-started/quick-start.md).
