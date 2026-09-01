# Verification (Claim Checking)

The verification stage runs between [gap analysis](gap-analysis.md) and
[citation export](citation-export.md). Before a report is generated,
each paper's key points are checked against that paper's own sources —
its abstract plus any grounded full-text passages from the
[fulltext stage](fulltext.md). Unsupported claims are flagged rather
than presented as fact.

## What readers see

- Flagged key points render with an _(unverified)_ marker in the
  thematic findings.
- The report's summary area carries an aggregate line, e.g.
  *Claim verification (heuristic): 11/12 key points supported by paper
  sources* — the `verification` field of the JSON report holds the same
  numbers (`claims_checked`, `claims_unverified`, `method`).

## How claims are checked

- **LLM** (when synthesis LLM mode is on and structured outputs are
  enabled) — a structured verdict per paper naming the claim numbers the
  sources do not support, judged strictly from the provided material.
- **Heuristic** (always available) — a claim is flagged when fewer than
  `min_term_coverage` of its content terms appear in the paper's
  sources. Flagging is deliberately conservative: with no sources at
  all, nothing is flagged, and abstract-derived heuristic findings pass
  by construction.

Identity note: verification never rewrites claims — it only annotates
`unverified_points` on the paper analyses and records the
`verification_summary` artifact consumed by report generation.

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `verification.enabled` | `true` | Toggle the stage |
| `verification.min_term_coverage` | `0.5` | Heuristic support threshold |

## Failure behavior

A failed LLM verdict falls back to the heuristic for that paper. The
stage passes gap-analysis output through unchanged, so downstream
stages are unaffected by verification results.
