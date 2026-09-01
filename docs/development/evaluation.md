# Evaluation Harness

The evaluation harness measures ranking quality against a labeled golden
dataset, giving every retrieval or ranking change a number instead of an
impression. It is the measurement layer called for by the
[improvement roadmap](roadmap.md) and runs offline — no network, no LLM —
so it works identically on developer machines and in CI.

## Golden dataset

`evals/golden_set.yaml` contains fourteen labeled queries spanning machine
learning, biomedicine, neuroscience, physics, speech, social science, and
computer vision. Each query lists candidate papers with a graded relevance
label:

- `2` — highly relevant, the papers a domain expert would expect first
- `1` — relevant supporting work
- `0` — real papers from other fields that keyword overlap could confuse

Candidates deliberately include hard negatives (for example, transformer
papers under a graph-neural-network query) so the metrics punish rankers
that match words rather than meaning.

## What the harness does

For each golden query, the harness feeds the candidates through the real
deduplication and ranking stages, then scores the resulting order against
the labels:

| Metric | Question it answers |
|--------|---------------------|
| Recall@5 | Do the relevant papers reach the top of the list? |
| nDCG@10 | Is the full ordering close to the ideal graded ordering? |
| MRR | How high does the first relevant paper appear? |
| Citation validity | Are DOIs well-formed, years plausible, locators present? |

Embeddings are used when the backend is installed; otherwise ranking falls
back to keyword signals, and the report labels which mode ran. The
`src.evaluation` package exposes `run_golden_evaluation()` for programmatic
use, and its module entry point prints the per-query table.

## Regression floors in CI

`tests/test_evaluation.py` asserts floor values below the measured
keyword-only baseline (with fourteen queries: mean R@5 0.94, nDCG@10 0.97,
MRR 1.00, validity 92%). A change that drops the suite below a floor has genuinely hurt
ranking quality and fails CI. When a deliberate improvement raises the
baseline, tighten the floors in the same change so the new level becomes
the protected one.

## Extending the dataset

Add queries where the ranker currently struggles: multi-concept queries,
fields outside machine learning, and queries whose relevant papers share
few title words with the query. Keep labels honest — the harness is only as
trustworthy as its dataset — and prefer real papers with verifiable
metadata; entries whose DOI cannot be stated with confidence carry none
rather than a guessed one. Growing toward the roadmap's ~20 queries
remains open, as does a live mode that resolves DOIs against CrossRef.
The module entry point accepts a JSON flag for automation, emitting
per-query metrics plus means.
