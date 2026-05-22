# Stage: query_expansion

Generates query variants and sub-questions to improve retrieval coverage.

| | |
|---|---|
| **Class** | `QueryExpansionStage` |
| **Module** | `src/research/query_expansion.py` |
| **Registry key** | `query_expansion` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `str \| QueryUnderstandingResult` | Uses `key_concepts` when understanding result provided |
| Output (`data`) | `ExpandedQuerySet` | Passed to retrieval |
| Artifacts written | `expanded_queries` | Debug visibility only |

## Behavior

Two-phase expansion:

1. **Heuristics always run** — synonym variants, concept permutations, sub-question templates
2. **Optional LLM pass** — when `query_expansion.llm_enabled`, calls `AgentRole.EXPANSION` for additional variants and sub-questions; merged with heuristic output (deduplicated, capped)

When LLM is disabled or fails, heuristic-only expansion is returned.

!!! warning "Settings inconsistency"
    `expand_query_llm()` reads `get_settings().llm` rather than `ctx.config.llm`. If settings differ between pipeline config and global singleton, LLM expansion may use unexpected provider/model.

## Configuration

| Key | Purpose |
|-----|---------|
| `query_expansion.llm_enabled` | Resolved at pipeline start from `llm_mode` + env |
| `query_expansion.llm_mode` | `auto` / `on` / `off` |
| `query_expansion.max_variants` | Cap on query variants |
| `query_expansion.max_sub_questions` | Cap on sub-questions |

Env overrides: `RA_QUERY_EXPANSION__LLM_ENABLED`, `RA_QUERY_EXPANSION__LLM_MODE`.

## LLM

Optional — `AgentRole.EXPANSION` when enabled. Heuristics always produce baseline expansion.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged.

## Metrics

- `variant_count`
- `sub_question_count`

## Related

- [Previous: query_understanding](query-understanding.md)
- [Next: retrieval](retrieval.md)
- [LLM layer](../llm-layer.md)
