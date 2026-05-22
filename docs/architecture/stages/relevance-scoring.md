# Stage: relevance_scoring

Filters ranked papers below composite relevance thresholds while ensuring a minimum corpus size.

| | |
|---|---|
| **Class** | `RelevanceScoringStage` |
| **Module** | `src/research/relevance_scoring.py` |
| **Registry key** | `relevance_scoring` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `list[RankedPaper]` | From ranking |
| Input (artifacts) | `query_understanding`, `query_embedding`, `paper_embeddings` | Concept matching + embedding floor |
| Output (`data`) | `list[RankedPaper]` | Filtered list |
| Artifacts written | `ranked_papers` (updated), `relevance_filter_reasons` | Reasons for excluded papers |

## Behavior

For each ranked paper, evaluates:

1. **Minimum rank score** — `relevance_scoring.min_rank_score`
2. **Embedding similarity floor** — `min_embedding_similarity`, optionally adaptive via `adaptive_embedding`
3. **Concept coverage** — key concepts from query understanding must appear in title/abstract

Papers failing any check are removed. If the filtered set falls below `min_keep_papers`, the relevance floor is relaxed to retain at least that many papers by combined score.

## Configuration

| Key | Purpose |
|-----|---------|
| `relevance_scoring.min_rank_score` | Minimum composite rank score |
| `relevance_scoring.min_embedding_similarity` | Embedding floor |
| `relevance_scoring.adaptive_embedding` | Adjust floor based on corpus distribution |
| `relevance_scoring.min_keep_papers` | Minimum papers to retain |
| `relevance_scoring.min_concept_match_ratio` | Required concept coverage |

## LLM

No.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged.

## Metrics

Filter counts and adaptive floor adjustments recorded in warnings.

## Related

- [Previous: ranking](ranking.md)
- [Next: clustering](clustering.md)
- [Data model: RankedPaper](../data-model.md)
