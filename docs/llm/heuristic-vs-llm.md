# Heuristic vs LLM

The pipeline can run query expansion, synthesis, and gap analysis with **heuristics** (no LLM tokens) or **LLM agents** (structured JSON via pydantic-ai). Default settings favor heuristics for speed and low-resource machines.

Source: `src/config/resolve_llm_features.py`, `src/research/query_expansion.py`, `src/analysis/synthesis.py`, `src/analysis/gap_analysis.py`.

## Default behavior

Out of the box on Ollama with `llama3.2:3b` (catalog fallback) and `llm_mode: auto`:

| Stage | LLM used? | Mechanism |
|-------|-----------|-----------|
| Query expansion | **No** | Synonym tables, acronym expansion, Jaccard gates |
| Synthesis | **No** | Abstract sentence extraction, embedding-aligned agreements |
| Gap analysis | **No** | Derived from heuristic synthesis fields |

Reports may contain placeholders such as *"Details inferred from abstract only"* and *"Cross-paper disagreement analysis limited in heuristic mode."*

!!! warning "Quality impact"
    A successful pipeline run with **zero LLM tokens** can still produce misleading executive summaries when retrieval returns off-topic papers. See [Known issues](../quality/known-issues.md) for the full analysis and fixes applied to heuristic paths.

## Feature flag resolution

`resolve_effective_settings()` runs once at pipeline start and sets `synthesis.llm_enabled` and `query_expansion.llm_enabled` on the config passed to all stages.

**Precedence** (per feature — synthesis and query expansion independently):

1. `RA_{SECTION}__LLM_ENABLED` env (`true`/`false`/`1`/`0`)
2. `llm_mode: on` → enabled; `llm_mode: off` → disabled
3. `llm_mode: auto` → rules below

### Auto-mode rules

| Provider | synthesis LLM | query expansion LLM |
|----------|---------------|---------------------|
| `openai`, `anthropic` | Always **on** | Always **on** |
| `ollama` | On if catalog entry has `synthesis.llm_enabled: true` | Same catalog hint |
| Other | **Off** | **Off** |

For Ollama, the resolved model name (after `auto` selection) determines catalog hints:

| Model | `llm_mode: auto` | `max_llm_papers` hint |
|-------|------------------|----------------------|
| `llama3.1:8b` | LLM **on** | 5 |
| `llama3.2:3b` | LLM **off** | 3 |

```bash
# Force LLM on any Ollama model
RA_SYNTHESIS__LLM_ENABLED=true
RA_QUERY_EXPANSION__LLM_ENABLED=true
```

## What each path does

### Query expansion

**Heuristic** (`expand_query_heuristic`):

- Domain synonym map and acronym expansion
- Phrase-aware variant generation with Jaccard overlap gate
- Broad-term guard to avoid degenerate single-word variants
- No API calls; deterministic for a given query

**LLM** (`AgentRole.EXPANSION`):

- Structured JSON: search variants + sub-questions
- Uses `ctx.config` LLM settings after resolution
- Falls back to heuristics on timeout or parse failure

### Synthesis (two-pass)

**Heuristic**:

- Extracts sentences from abstracts aligned with query concepts
- Aggregates agreements from top-quartile embedding-similar papers
- Limited cross-paper disagreement analysis
- No per-paper deep reading

**LLM**:

- **Pass A** (`AgentRole.EXTRACTION`): structured per-paper analysis (up to `max_llm_papers`)
- **Pass B** (`AgentRole.SYNTHESIS`): cross-paper synthesis JSON
- Parallel workers controlled by `synthesis.concurrency`
- Timeout recovery via `src/core/stage_recovery.py`

### Gap analysis

!!! info "Coupled to synthesis"
    Gap analysis LLM is gated by **`synthesis.llm_enabled`**, not a separate `gap_analysis.llm_mode`. When synthesis LLM is off, gap analysis uses heuristics derived from synthesis output.

**Heuristic gap analysis**: infers gaps from synthesis agreement/disagreement fields.

**LLM gap analysis** (`AgentRole.GAP_ANALYSIS`): structured gaps and research opportunities JSON.

## Quality tradeoffs

| Dimension | Heuristic | LLM |
|-----------|-----------|-----|
| Speed | ~seconds for synthesis stage | Minutes on local 8B; faster on cloud |
| RAM / cost | Minimal | 8–10 GB RAM (local 8B) or API fees (cloud) |
| Query expansion | Good for common CS/ML terms | Better for niche or interdisciplinary queries |
| Synthesis depth | Abstract snippets only | Per-paper extraction + cross-paper reasoning |
| Disagreement analysis | Placeholder text | LLM compares conflicting claims |
| Failure mode | Can rank/ summarize off-topic papers | Same retrieval issues, but richer analysis when papers are relevant |

## When to enable LLM

| Goal | Suggested config |
|------|------------------|
| Fast scan, low RAM | Defaults (3B + heuristic) — [Cookbook recipe 1](../user-guide/configuration-cookbook.md) |
| Local quality | `llama3.1:8b` + catalog auto or `RA_SYNTHESIS__LLM_ENABLED=true` — [Recipe 2](../user-guide/configuration-cookbook.md) |
| Best quality | Cloud OpenAI/Anthropic — [Recipe 3](../user-guide/configuration-cookbook.md) |
| Debug heuristic-only bugs | Keep LLM off; inspect `logs/debug/` pipeline dumps |

## Configuration reference

| Variable | Default | Effect |
|----------|---------|--------|
| `RA_SYNTHESIS__LLM_MODE` | `auto` | Tri-state synthesis LLM |
| `RA_SYNTHESIS__LLM_ENABLED` | unset | Force override |
| `RA_SYNTHESIS__MAX_LLM_PAPERS` | `3` | Cap LLM extraction pass |
| `RA_QUERY_EXPANSION__LLM_MODE` | `auto` | Tri-state expansion LLM |
| `RA_QUERY_EXPANSION__LLM_ENABLED` | unset | Force override |

YAML equivalents under `synthesis:` and `query_expansion:` in `config/default.yaml`. See [Stage toggles](../configuration/stage-toggles.md).

## Structured outputs

When the LLM path runs, output schemas are enforced natively: the pydantic
model is attached to the agent (`output_type`), pydantic-ai validates the
response and retries with validation feedback on schema violations, and the
caller receives a typed object or falls back to heuristics. This is the only
LLM call path — the legacy prose-JSON repair machinery has been retired.
Identity fields (paper ID, title) are always taken from retrieval metadata,
never from model output.

## Verify LLM is active

Check pipeline logs or debug JSON in `logs/debug/`:

- Log line: `Resolved LLM features (provider=..., model=...): synthesis=True, query_expansion=True`
- Metrics: non-zero `llm_tokens_in` / `llm_tokens_out` in pipeline metrics

Enable debug and inspect dumps: [Logging and debug — Debug walkthrough](../operations/logging-and-debug.md#debug-walkthrough).

## Related pages

- [Ollama](ollama.md) — catalog hints for auto mode
- [Cloud providers](cloud-providers.md) — auto-enables LLM
- [Synthesis stage](../architecture/stages/synthesis.md) — two-pass workflow
- [Known issues](../quality/known-issues.md) — heuristic quality RCA
