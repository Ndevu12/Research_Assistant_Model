# Troubleshooting

Consolidated FAQ for common setup, runtime, and quality issues. Command snippets link to the [root README](https://github.com/Ndevu12/Research_Assistant_Model#quick-start); this page focuses on diagnosis.

## Setup and dependencies

### "Not running inside Pipenv" warning

Always use Pipenv so dependencies (especially `sentence-transformers`) are available. See [README Quick Start](https://github.com/Ndevu12/Research_Assistant_Model#quick-start) and [CLI reference](../user-guide/cli.md).

Plain `python -m src` may miss packages installed only in the Pipenv virtualenv.

### Missing `sentence-transformers` / import errors

Run `pipenv install`, then verify with [Setup system — Quick start](../setup-system/index.md#quick-start).

Embedding stages require `sentence-transformers` and will fail or degrade without it.

### Setup directory not found

The CLI expects `setups/` at the project root. Run commands from the repository root, not from `src/`.

---

## Ollama (default LLM)

### Ollama not installed or not running

Use [Setup system — Quick start](../setup-system/index.md#quick-start), or manually: `ollama serve` and `ollama pull llama3.1:8b`.

First CLI run with `RA_LLM__PROVIDER=ollama` triggers automatic setup via `ensure_setup()` in `src/__main__.py`.

### Wrong or missing model

| Symptom | Fix |
|---------|-----|
| Model not installed | Set `RA_LLM__MODEL=auto` or run `ollama pull <model>` |
| Too slow / OOM | Use `RA_LLM__MODEL=llama3.2:3b` or let `auto` pick a smaller model |
| Wrong model selected | Check `config/ollama_models.yaml` priorities and your RAM |

Pin a model via [Setup system](../setup-system/index.md#quick-start) (`manager --model …`).

### Skipping Ollama setup

Cloud providers skip local setup automatically:

```bash
RA_LLM__PROVIDER=openai
OPENAI_API_KEY=sk-...
```

---

## Retrieval

### No papers returned

1. Check network connectivity
2. Try a broader query
3. Enable debug and inspect `logs/debug/pipeline_*.json` → `stage_results.retrieval`
4. Look for provider warnings in `logs/combined_*.log`

### Semantic Scholar rate limits

Set `S2_API_KEY` in `.env` for higher limits. The client retries on 429 with `Retry-After` backoff.

### CrossRef empty or slow results

Set polite-pool mailto:

```bash
RA_CROSSREF_MAILTO=you@example.com
```

### arXiv / CrossRef not used from CLI batch mode

!!! info "CLI vs full pipeline"
    `python -m src "query"` only queries OpenAlex + Semantic Scholar. Use interactive mode, the API, or programmatic `run_research()` to enable other providers.

### Enabled stub provider (PubMed, CORE, DBLP)

Enabling a stub logs a warning and returns no papers from that provider. Disable in YAML/env until implemented.

---

## Report quality

### Report feels shallow or generic

Default config keeps **heuristic synthesis** (`RA_SYNTHESIS__LLM_ENABLED=false`). Enable LLM stages per [Heuristic vs LLM](../llm/heuristic-vs-llm.md) and [Configuration cookbook](../user-guide/configuration-cookbook.md#2-high-quality-local-8b-llm-synthesis).

See also [Known issues](../quality/known-issues.md).

### Partial pipeline / warning icons in progress

Stages can complete with ⚠ when:

- A retrieval provider failed (others may still succeed)
- A stage timed out (`stage_timeout_seconds` / `synthesis_timeout_seconds`)
- Heuristic recovery ran (`continue_on_stage_failure=true`)

Inspect debug dumps or error logs for the specific stage warning.

---

## Output and formats

### HTML/PDF printed to terminal

Use `--output` for file output. See [Output formats](../user-guide/output-formats.md) and [README Output Format](https://github.com/Ndevu12/Research_Assistant_Model#output-format).

`--format pdf` produces print-ready HTML — open in a browser → Print → Save as PDF.

### Citation exports

See [Output formats — Citation exports](../user-guide/output-formats.md#citation-exports-export).

---

## Configuration surprises

### YAML change has no effect

Check precedence: env vars and `.env` override YAML. Verify with debug dump `config` section or temporarily unset conflicting env keys.

### Debug always on after copying `.env.example`

`.env.example` sets `RA_DEBUG=1`. Comment it out or set `RA_DEBUG=0`.

### `per_provider_limit` vs provider `limit`

Only `RA_RETRIEVAL__PER_PROVIDER_LIMIT` controls search result counts. Per-provider `limit` in YAML is ignored.

---

## Logs and debug

```bash
tail -f logs/combined_$(date +%Y%m%d).log
ls logs/debug/
```

Full debug walkthrough (including `RA_PIPELINE__DEBUG` run command): [Logging and debug](logging-and-debug.md).

## Health check reference

Check matrix and diagnostics: [Health check](../getting-started/health-check.md). Commands: [Setup system](../setup-system/index.md#quick-start).

See also: [Known issues](../quality/known-issues.md).
