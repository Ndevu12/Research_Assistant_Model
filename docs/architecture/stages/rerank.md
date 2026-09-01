# Rerank (Cross-Encoder)

The rerank stage runs between [snowball](snowball.md) and
[relevance scoring](relevance-scoring.md), completing the two-stage
retrieval pattern: ranking is the fast first pass over the whole candidate
pool (embeddings plus weighted signals, now including a BM25 lexical
signal), and the cross-encoder is the slow, accurate second pass over just
the top of the list.

A cross-encoder reads the query and each paper *together* through one
model, so it judges relevance far better than any similarity between
separately-computed vectors — but at a per-pair cost that only makes sense
for a shortlist.

## Scoring and blending

The top `top_n` ranked papers are scored against the query (title plus the
first 1,000 abstract characters). Scores are min–max normalized and
blended with the first-pass rank score:

```
final = blend_weight × cross_encoder + (1 − blend_weight) × rank_score
```

Blending — rather than replacing — keeps citation, recency, and venue
signals in the final order. Each reranked paper records
`cross_encoder_score` and `pre_rerank_score` in its score breakdown, and
papers beyond `top_n` keep their original order.

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `rerank.enabled` | `true` | Toggle the stage |
| `rerank.model` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Any sentence-transformers cross-encoder |
| `rerank.top_n` | `25` | Papers scored by the cross-encoder |
| `rerank.blend_weight` | `0.5` | Cross-encoder share of the final score |

The default model is compact (~90 MB) and CPU-friendly, fitting the
local-first posture; stronger rerankers (e.g. `BAAI/bge-reranker-base`)
drop in via `rerank.model` once measured against the
[evaluation harness](../../development/evaluation.md).

## Failure behavior

Reranking never blocks a run. When `sentence-transformers` is not
installed, or model loading/scoring fails, the stage passes the original
ranking through with a warning — the same graceful degradation the
embedding-backed stages use.

## BM25 in the first pass

Alongside this stage, ranking gained a `lexical_bm25` signal: Okapi BM25
computed over the candidate corpus, normalized per query, weighted at
`0.08` (validated against the golden set — higher weights measurably cost
nDCG). BM25 contributes proper term-frequency and inverse-document-
frequency evidence that plain keyword-overlap ratios miss.
