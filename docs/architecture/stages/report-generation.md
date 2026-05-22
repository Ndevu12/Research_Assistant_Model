# Stage: report_generation

Assembles the final `EnhancedResearchReport` from all pipeline artifacts.

| | |
|---|---|
| **Class** | `ReportGenerationStage` |
| **Module** | `src/reporting/report_generation.py` |
| **Registry key** | `report_generation` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `dict[str, str]` | Citation exports from citation_export |
| Input (artifacts) | `synthesis_result`, `gap_analysis`, `paper_clusters`, `paper_analyses`, `ranked_papers`, `citation_index` | Full report assembly |
| Output (`data`) | `EnhancedResearchReport` | Final pipeline output |
| Artifacts written | `enhanced_report` | Exported in `ResearchPipelineResult` |

## Behavior

`assemble_report()` combines artifacts into a structured report:

| Report field | Source |
|--------------|--------|
| `executive_summary` | Built from synthesis + embedding-filtered top papers |
| `papers` | `paper_analyses` artifact |
| `clusters` | `paper_clusters` artifact |
| `synthesis` | `synthesis_result` artifact |
| `gap_analysis` | `gap_analysis` artifact |
| `gaps`, `timeline` | Derived from synthesis and paper years |
| `citation_index` | From artifact or rebuilt |
| `exports` | Citation exports from data chain |

Executive summary uses `relevance_scoring.min_embedding_similarity` as an embedding floor for selecting top papers to highlight.

Deterministic assembly — no LLM calls.

## Configuration

| Key | Purpose |
|-----|---------|
| `relevance_scoring.min_embedding_similarity` | Executive summary embedding floor |

## LLM

No — deterministic assembly.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

On failure, returns prior `data` unchanged.

## Metrics

- `paper_count`
- `cluster_count`

## Downstream rendering

The CLI and API render `EnhancedResearchReport` via:

- `render_enhanced_markdown()` — default markdown output
- `render_report_output()` — markdown, JSON, HTML, PDF-ready formats

See [Output formats](../../user-guide/output-formats.md).

## Related

- [Previous: citation_export](citation-export.md)
- [Data model: EnhancedResearchReport](../data-model.md)
- [Architecture overview](../overview.md)
