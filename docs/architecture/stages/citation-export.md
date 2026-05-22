# Stage: citation_export

Generates citation exports and a citation index from ranked papers.

| | |
|---|---|
| **Class** | `CitationExportStage` |
| **Module** | `src/reporting/citations.py` |
| **Registry key** | `citation_export` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `GapAnalysisResult` | Passed through from gap_analysis |
| Input (artifact) | `ranked_papers` | Source papers for citation generation |
| Output (`data`) | `dict[str, str]` | Format name → export content |
| Artifacts written | `citation_exports`, `citation_index` | Used by report_generation |

## Behavior

1. Extracts `RetrievedPaper` objects from `ranked_papers` artifact
2. Builds citation index (citation key → paper ID) via `build_citation_index()`
3. Generates exports for all `SUPPORTED_FORMATS` (BibTeX, CSL JSON, etc.) via `generate_citation_exports()`

Deterministic — no LLM calls. The gap analysis result on the data chain is not used directly; this stage reads papers from artifacts.

## Configuration

No stage-specific config keys.

## LLM

No — BibTeX/CSL via `generate_citation_exports`.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged.

## Metrics

- `citation_count` — number of entries in citation index

## Related

- [Previous: gap_analysis](gap-analysis.md)
- [Next: report_generation](report-generation.md)
- [Output formats](../../user-guide/output-formats.md)
