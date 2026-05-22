# Stage: query_understanding

Extracts structured intent, constraints, and key concepts from the raw user query.

| | |
|---|---|
| **Class** | `QueryUnderstandingStage` |
| **Module** | `src/research/query_understanding.py` |
| **Registry key** | `query_understanding` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `str` | Raw query (initial pipeline input) |
| Output (`data`) | `QueryUnderstandingResult` | Passed to query_expansion |
| Artifacts written | `query_understanding` | Read by relevance_scoring |

## Behavior

Pure heuristic — no LLM calls. Uses regex and keyword extraction:

- **Intent detection:** `literature_review` (default), `comparison` (compare/versus/vs), or `gap_analysis` (gap/opportunity keywords)
- **Year constraints:** explicit years, `after YYYY`, `before YYYY`
- **Key concepts:** extracted via `extract_core_concepts()` shared with query expansion

## Configuration

No stage-specific config keys. Always runs when enabled.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged (no dedicated recovery path).

## Metrics

- `intent` — detected intent string
- `concept_count` — number of key concepts

## Related

- [Next: query_expansion](query-expansion.md)
- [Data model: QueryUnderstandingResult](../data-model.md)
- [Pipeline stages](../pipeline-stages.md)
