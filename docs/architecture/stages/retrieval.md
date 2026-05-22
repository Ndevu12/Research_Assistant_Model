# Stage: retrieval

Searches enabled scholarly providers concurrently and merges results.

| | |
|---|---|
| **Class** | `RetrievalStage` |
| **Module** | `src/retrieval/retrieval_stage.py` |
| **Registry key** | `retrieval` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `ExpandedQuerySet` | Original + variants + sub-questions searched |
| Input (artifact) | `cached_papers` | Session cache bypass — skips provider calls |
| Output (`data`) | `list[RetrievedPaper]` | Merged, deduplicated at provider level |
| Artifacts written | `retrieved_papers` | Used by synthesis recovery |

## Behavior

1. If `cached_papers` artifact exists, validates and returns cached papers immediately (cache hit).
2. Otherwise, builds query list from `ExpandedQuerySet` (original + variants + sub-questions).
3. For each enabled provider in config, searches all queries concurrently (bounded by `concurrency_limit`).
4. Provider failures are collected as warnings; partial results continue.
5. All provider results are merged into a single list.

!!! warning "Per-provider limit caveat"
    The stage always passes `settings.retrieval.per_provider_limit` to `provider.search()`. Per-provider `limit` values in YAML are **ignored** at the stage level.

## Configuration

| Key | Purpose |
|-----|---------|
| `retrieval.concurrency_limit` | Max concurrent provider requests |
| `retrieval.per_provider_limit` | Papers per provider per query |
| `retrieval.providers.{name}.enabled` | Enable/disable each provider |

See [Provider matrix](../../retrieval/provider-matrix.md) for live vs stub providers.

## LLM

No.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On total failure, returns empty list with `partial=True` and warning.

## Metrics

- `papers_found`
- `providers_failed`
- `cache_hit` (when applicable)

## Related

- [Previous: query_expansion](query-expansion.md)
- [Next: deduplication](deduplication.md)
- [Retrieval overview](../../retrieval/overview.md)
