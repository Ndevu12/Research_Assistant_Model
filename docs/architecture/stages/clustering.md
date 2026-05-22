# Stage: clustering

Groups ranked papers into thematic clusters for synthesis and report structure.

| | |
|---|---|
| **Class** | `ClusteringStage` |
| **Module** | `src/research/clustering.py` |
| **Registry key** | `clustering` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `list[RankedPaper]` | From relevance_scoring |
| Input (artifact) | `paper_embeddings` | Reused from ranking when available |
| Output (`data`) | `list[PaperCluster]` | Thematic groups |
| Artifacts written | `paper_clusters` | Read by synthesis, gap_analysis, report_generation |

## Behavior

Primary algorithm: **HDBSCAN** on paper embedding vectors when sentence-transformers is available and embeddings exist.

Fallback: single keyword-based theme group when embeddings are unavailable or clustering produces no clusters.

Each cluster includes a `theme` label, `summary`, and list of member `paper_ids`.

## Configuration

| Key | Purpose |
|-----|---------|
| `clustering.min_cluster_size` | HDBSCAN minimum cluster size |
| `clustering.min_samples` | HDBSCAN density parameter |
| `embedding.*` | Embedding model (if re-computing) |
| `ranking.*` | Used by `ensure_ranked_papers` adapter |

## LLM

No — HDBSCAN + keyword fallback.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

Empty input returns empty cluster list. On failure, returns prior `data` unchanged.

## Metrics

- `num_clusters`

## Related

- [Previous: relevance_scoring](relevance-scoring.md)
- [Next: synthesis](synthesis.md)
- [Data model: PaperCluster](../data-model.md)
