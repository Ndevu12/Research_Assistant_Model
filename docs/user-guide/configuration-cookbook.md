# Configuration Cookbook

Copy-paste recipes for common setups. Each recipe shows **environment variables** and equivalent **YAML** where applicable.

Precedence reminder: env > `.env` > YAML > defaults. See [Configuration precedence](../configuration/precedence.md).

!!! tip "Pick your entry point first"
    Batch CLI (`python -m src "query"`) only uses OpenAlex + Semantic Scholar regardless of provider recipes below. For recipes that enable arXiv/CrossRef or extra providers, use **interactive mode**, the **API**, or programmatic `run_research()`. See [CLI vs API](cli-vs-api.md).

---

## 1. Fast local (default heuristic)

Minimal config — Ollama auto model, heuristic synthesis, OpenAlex + S2 only on CLI batch path.

**.env:**

```bash
RA_LLM__PROVIDER=ollama
RA_LLM__MODEL=auto
RA_SYNTHESIS__LLM_ENABLED=false
RA_QUERY_EXPANSION__LLM_ENABLED=false
RA_PIPELINE__STREAM_PROGRESS=true
```

**Run:** [README Usage](https://github.com/Ndevu12/Research_Assistant_Model#usage) or [CLI reference](cli.md).

**Best for:** Quick scans, low RAM (`llama3.2:3b`), offline-after-setup use.

---

## 2. High-quality local (8B + LLM synthesis)

Enable LLM stages when `llama3.1:8b` is selected (catalog sets `synthesis.llm_enabled: true` for 8B).

**.env:**

```bash
RA_LLM__PROVIDER=ollama
RA_LLM__MODEL=llama3.1:8b
RA_SYNTHESIS__LLM_ENABLED=true
RA_QUERY_EXPANSION__LLM_ENABLED=true
RA_SYNTHESIS__MAX_LLM_PAPERS=5
```

**Verify model:** [Setup system](../setup-system/index.md#quick-start) (`health_check --model llama3.1:8b`).

**Best for:** Richer synthesis on capable hardware (8–10 GB RAM).

---

## 3. Cloud OpenAI quality

Skip Ollama; use GPT for expansion and synthesis.

**.env:**

```bash
RA_LLM__PROVIDER=openai
RA_LLM__MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
RA_SYNTHESIS__LLM_ENABLED=true
RA_QUERY_EXPANSION__LLM_ENABLED=true
RA_RANKING__TOP_K=30
```

**Run:** [CLI reference](cli.md) (same query invocations as README Usage).

**Best for:** Maximum quality without local GPU/RAM. API costs apply.

---

## 4. Enable arXiv + CrossRef (full pipeline)

!!! info "Not available on CLI batch shortcut"
    Use **interactive mode**, **API**, or programmatic `run_research()` — not `python -m src "query"` alone.

**YAML** (`config/providers.yaml`):

```yaml
concurrency_limit: 4
per_provider_limit: 10
providers:
  openalex:
    enabled: true
  semantic_scholar:
    enabled: true
  arxiv:
    enabled: true
  crossref:
    enabled: true
```

**Equivalent .env:**

```bash
RA_RETRIEVAL__PROVIDERS__ARXIV__ENABLED=true
RA_RETRIEVAL__PROVIDERS__CROSSREF__ENABLED=true
RA_RETRIEVAL__PER_PROVIDER_LIMIT=10
RA_CROSSREF_MAILTO=you@example.com
S2_API_KEY=optional_for_rate_limits
```

**Run (interactive — full settings):** [Interactive sessions](interactive-sessions.md) (`pipenv run python -m src` with no query arg).

Or use the [API](../api/index.md) / programmatic path. See [CLI vs API](cli-vs-api.md).

---

## 5. Debug mode (inspect pipeline artifacts)

**.env:**

```bash
RA_PIPELINE__DEBUG=true
RA_PIPELINE__STREAM_PROGRESS=true
# Avoid duplicate: do not also set RA_DEBUG=1 unless intentional
```

**Run and inspect:** [Logging and debug walkthrough](../operations/logging-and-debug.md#debug-walkthrough), then:

```bash
ls -lt logs/debug/
jq '.stage_results | keys' logs/debug/pipeline_*.json
```

---

## 6. Retrieval-only smoke test

Disable analysis/report stages to validate API connectivity quickly.

**YAML snippet** (merge into `default.yaml` or use env):

```yaml
pipeline:
  enabled_stages:
    query_understanding: true
    query_expansion: true
    retrieval: true
    deduplication: true
    ranking: true
    relevance_scoring: false
    clustering: false
    synthesis: false
    gap_analysis: false
    citation_export: false
    report_generation: false
```

**Env alternative (disable later stages):**

```bash
RA_PIPELINE__ENABLED_STAGES__CLUSTERING=false
RA_PIPELINE__ENABLED_STAGES__SYNTHESIS=false
RA_PIPELINE__ENABLED_STAGES__GAP_ANALYSIS=false
RA_PIPELINE__ENABLED_STAGES__CITATION_EXPORT=false
RA_PIPELINE__ENABLED_STAGES__REPORT_GENERATION=false
```

Use debug dumps to inspect `artifacts.retrieved_papers`.

---

## 7. Session memory + retrieval cache

**.env:**

```bash
RA_MEMORY__CACHE_ENABLED=true
RA_MEMORY__DB_PATH=data/research.db
```

**Interactive:** [Interactive sessions](interactive-sessions.md).

Repeat the same query in a new session run may skip network retrieval when config hash matches.

---

## 8. Quiet CI / scripting

Disable progress via env and CLI flag — see [Progress streaming](../operations/progress-streaming.md#enabling-and-disabling) and [CLI reference](cli.md#progress-output). Example redirect:

```bash
RA_PIPELINE__STREAM_PROGRESS=false
RA_PIPELINE__DEBUG=false
pipenv run python -m src --no-progress --format json "query" > report.json
```

---

## Recipe picker

| Goal | Recipe |
|------|--------|
| Fastest offline run | #1 Fast local |
| Best local quality | #2 High-quality local |
| Best overall quality | #3 Cloud OpenAI |
| More paper sources | #4 arXiv + CrossRef |
| Diagnose failures | #5 Debug mode |
| Test APIs only | #6 Retrieval smoke test |
| Repeat queries faster | #7 Session cache |

See also: [CLI vs API](cli-vs-api.md), [Environment variables](../configuration/environment-variables.md), [Heuristic vs LLM](../llm/heuristic-vs-llm.md), [Provider matrix](../retrieval/provider-matrix.md).
