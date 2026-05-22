# Stage: deduplication

Removes duplicate papers from the retrieved set using metadata matching and optional embedding similarity.

| | |
|---|---|
| **Class** | `DeduplicationStage` |
| **Module** | `src/retrieval/deduplication.py` |
| **Registry key** | `deduplication` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `list[RetrievedPaper]` | From retrieval |
| Output (`data`) | `list[RetrievedPaper]` | Deduplicated list |
| Artifacts written | `deduplication_stats` | Counts: input, metadata_removed, embedding_removed, output |

## Behavior

Two deduplication passes when enabled:

1. **Metadata union-find** — groups papers by DOI, normalized title, or URL overlap; keeps highest-citation representative
2. **Embedding similarity** (optional) — when `enable_embedding_dedup` is true and sentence-transformers is installed, removes papers above `embedding_similarity_threshold`

If deduplication is disabled (`deduplication.enabled: false`), papers pass through unchanged.

## Configuration

| Key | Purpose |
|-----|---------|
| `deduplication.enabled` | Master toggle |
| `deduplication.enable_embedding_dedup` | Enable embedding-based dedup |
| `deduplication.embedding_similarity_threshold` | Cosine similarity cutoff |
| `embedding.*` | Embedding model config when embedding dedup runs |

## LLM

No — metadata union-find + optional embedding similarity.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged.

## Metrics

Full `deduplication_stats` dict passed as stage metrics.

## Related

- [Previous: retrieval](retrieval.md)
- [Next: ranking](ranking.md)
- [Data model: RetrievedPaper](../data-model.md)
