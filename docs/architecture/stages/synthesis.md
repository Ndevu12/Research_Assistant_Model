# Stage: synthesis

Runs two-pass cross-paper synthesis: per-paper extraction followed by collective synthesis.

| | |
|---|---|
| **Class** | `SynthesisStage` |
| **Module** | `src/analysis/synthesis.py` |
| **Registry key** | `synthesis` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `list[PaperCluster]` | From clustering |
| Input (artifacts) | `ranked_papers` | Primary paper source; falls back to `retrieved_papers` |
| Output (`data`) | `SynthesisResult` | Passed to gap_analysis |
| Artifacts written | `paper_extractions`, `paper_analyses`, `synthesis_result`; may refresh `ranked_papers` on recovery |

## Behavior

### LLM mode (when `synthesis.llm_enabled`)

Two-pass flow capped at `max_llm_papers`:

1. **Pass A — Extraction** (`AgentRole.EXTRACTION`): concurrent per-paper structured extraction (methodology, datasets, benchmarks, limitations, findings)
2. **Pass B — Synthesis** (`AgentRole.SYNTHESIS`): collective cross-paper synthesis JSON (agreements, disagreements, trends, gaps, datasets, methodologies)

Circuit breaker and retry logic protect against cascading LLM failures.

### Heuristic mode (default for small Ollama models)

Extracts key points from abstracts and titles without LLM calls. Produces placeholder text such as *"Details inferred from abstract only"* in downstream report sections.

### Recovery paths

- If `ranked_papers` artifact is empty, attempts recovery from `retrieved_papers` via `ensure_ranked_papers()`
- On timeout/cancellation/exception: `recover_synthesis_output()` produces heuristic partial output
- Pipeline-level timeout triggers `recover_stage_output()` in `src/core/stage_recovery.py`

## Configuration

| Key | Purpose |
|-----|---------|
| `synthesis.llm_enabled` | Resolved at pipeline start |
| `synthesis.llm_mode` | `auto` / `on` / `off` |
| `synthesis.max_llm_papers` | Cap on LLM extraction calls |
| `synthesis.concurrency` | Parallel extraction limit |
| `synthesis.circuit_breaker_failures` | Failures before circuit opens |
| `llm.*` | Provider/model for agents |

Env overrides: `RA_SYNTHESIS__LLM_ENABLED`, `RA_SYNTHESIS__LLM_MODE`.

## LLM

Two-pass when enabled: `AgentRole.EXTRACTION` → `AgentRole.SYNTHESIS`. Heuristic fallback when disabled or on failure.

## Timeout

**`pipeline.synthesis_timeout_seconds`** (default **600 s**) — longer than all other stages.

## Recovery

Dedicated heuristic recovery via `recover_synthesis_output()` and `src/core/stage_recovery.py`.

## Metrics

Synthesis mode, paper count, extraction count recorded in stage metrics and logs.

## Related

- [Previous: clustering](clustering.md)
- [Next: gap_analysis](gap-analysis.md)
- [LLM layer](../llm-layer.md)
- [Heuristic vs LLM](../../llm/heuristic-vs-llm.md)
- [Quality: known issues](../../quality/known-issues.md)
