# Stage: ranking

Scores and ranks deduplicated papers using a weighted composite of multiple signals.

| | |
|---|---|
| **Class** | `RankingStage` |
| **Module** | `src/research/ranking.py` |
| **Registry key** | `ranking` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `list[RetrievedPaper]` | From deduplication |
| Output (`data`) | `list[RankedPaper]` | Top-K by composite score |
| Artifacts written | `ranked_papers`, `query_embedding`, `paper_embeddings` | Embeddings reused downstream |

## Behavior

Computes a weighted composite score per paper:

| Signal | Config weight key |
|--------|-------------------|
| Embedding similarity to query | `ranking.weights.embedding_similarity` |
| Citation count | `ranking.weights.citation_count` |
| Recency | `ranking.weights.recency` |
| Keyword overlap | `ranking.weights.keyword_overlap` |
| Venue quality | `ranking.weights.venue_quality` |

Additional tuning: `domain_penalty_multiplier`, `outlier_embedding_gap`, `keyword_collision_max_sim`, `canonical_boost`.

Results are sorted and truncated to `ranking.top_k`. Query and paper embeddings are stored via `store_ranking_embedding_result()` for reuse by relevance_scoring and clustering.

If sentence-transformers is unavailable and embedding weight > 0, falls back to keyword-only ranking with a warning.

## Configuration

| Key | Purpose |
|-----|---------|
| `ranking.top_k` | Maximum papers to pass downstream |
| `ranking.weights.*` | Signal weight overrides |
| `embedding.*` | Embedding model for similarity scoring |

## LLM

No.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On `ImportError`, retries with keyword-only fallback. On other failure, returns prior `data` unchanged.

## Metrics

- `top_score` — highest rank_score in output

## Related

- [Previous: deduplication](deduplication.md)
- [Next: relevance_scoring](relevance-scoring.md)
- [Artifacts: embedding storage](../artifacts.md)
