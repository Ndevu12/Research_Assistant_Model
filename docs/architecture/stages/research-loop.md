# Research Loop (Coverage-Driven Refinement)

The research loop runs between [relevance scoring](relevance-scoring.md)
and [fulltext](fulltext.md). It turns the one-shot pipeline into the
assess–refine–stop cycle deep-research agents use: after filtering, the
stage judges whether the kept papers actually answer the query; when
coverage is thin it generates targeted follow-up queries, retrieves for
them, and merges the new candidates through the same deduplication,
ranking, and relevance machinery — repeating up to a configured budget.

## Coverage assessment

Two assessors, chosen by the LLM feature resolution:

- **LLM** (when synthesis LLM mode is on and structured outputs are
  enabled) — a structured verdict: `sufficient`, `missing_aspects`, and
  `follow_up_queries` proposed as concise academic search phrases.
- **Heuristic** (always available) — coverage requires at least
  `min_sufficient_papers` kept papers *and* every core query concept
  matched by at least one paper; follow-up queries combine each missing
  concept with the covered ones.

The final assessment is stored in the `coverage_assessment` artifact, so
debug dumps show why the loop did or did not fire.

## Refinement round

Follow-up queries go through the standard retrieval fan-out, and the new
candidates merge with the current set through deduplication (with
cross-provider reconciliation), ranking, and the relevance filter — no
special-case scoring path. Embedding-backend failures fall back to
keyword ranking exactly as the ranking stage does.

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `research_loop.enabled` | `true` | Toggle the stage |
| `research_loop.max_iterations` | `1` | Refinement rounds per run |
| `research_loop.min_sufficient_papers` | `6` | Heuristic floor for sufficiency |
| `research_loop.max_follow_up_queries` | `3` | Queries retrieved per round |

## Failure behavior

Retrieval failures during a refinement round pass the current ranking
through with a warning; an assessment that never reaches sufficiency
stops at the iteration budget. Stage metrics record iterations run, the
follow-up queries used, and whether coverage ended sufficient.
