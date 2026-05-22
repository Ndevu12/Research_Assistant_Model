# Data Model

All pipeline types are Pydantic `BaseModel` classes defined in `src/retrieval/models.py`. Stages pass typed objects through the sequential `data` chain and store additional objects in the artifact store.

## Type flow through the pipeline

| Stage | `data` input | `data` output |
|-------|--------------|---------------|
| query_understanding | `str` | `QueryUnderstandingResult` |
| query_expansion | `str \| QueryUnderstandingResult` | `ExpandedQuerySet` |
| retrieval | `ExpandedQuerySet` | `list[RetrievedPaper]` |
| deduplication | `list[RetrievedPaper]` | `list[RetrievedPaper]` |
| ranking | `list[RetrievedPaper]` | `list[RankedPaper]` |
| relevance_scoring | `list[RankedPaper]` | `list[RankedPaper]` |
| clustering | `list[RankedPaper]` | `list[PaperCluster]` |
| synthesis | `list[PaperCluster]` | `SynthesisResult` |
| gap_analysis | `SynthesisResult` | `GapAnalysisResult` |
| citation_export | `GapAnalysisResult` | `dict[str, str]` |
| report_generation | `dict[str, str]` | `EnhancedResearchReport` |

## Core types

### RetrievedPaper

Paper retrieved from a scholarly API provider.

| Field | Type | Notes |
|-------|------|-------|
| `title` | `str` | Required |
| `abstract` | `Optional[str]` | May be absent for metadata-only records |
| `year` | `Optional[int]` | Publication year |
| `venue` | `Optional[str]` | Journal or conference |
| `url` | `Optional[str]` | Landing page |
| `doi` | `Optional[str]` | Preferred stable ID |
| `provider` | `str` | Source provider name (alias: `source`) |
| `citation_count` | `Optional[int]` | When available from provider |
| `authors` | `list[str]` | Author names |
| `keywords` | `list[str]` | Subject keywords |
| `embedding_id` | `Optional[str]` | Internal embedding cache key |
| `raw_metadata` | `dict[str, Any]` | Provider-specific payload |

**Computed properties:**

- `source` — backward-compatible alias for `provider`
- `paper_id` — stable ID: `doi` → `url` → `title`

### RankedPaper

Wraps a `RetrievedPaper` with ranking signals.

| Field | Type | Notes |
|-------|------|-------|
| `paper` | `RetrievedPaper` | Underlying paper |
| `rank_score` | `float` | Composite ranking score |
| `score_breakdown` | `dict[str, float]` | Per-signal contributions (embedding, citations, recency, etc.) |

### QueryUnderstandingResult

Structured query analysis from stage 1.

| Field | Type | Notes |
|-------|------|-------|
| `intent` | `str` | `literature_review`, `comparison`, or `gap_analysis` |
| `constraints` | `dict[str, Any]` | Year filters (`years`, `min_year`, `max_year`) |
| `key_concepts` | `list[str]` | Extracted core concepts |

### ExpandedQuerySet

Query variants for multi-query retrieval.

| Field | Type | Notes |
|-------|------|-------|
| `original` | `str` | User query |
| `variants` | `list[str]` | Rephrased search strings |
| `sub_questions` | `list[str]` | Decomposed sub-queries |

### PaperCluster

Thematic grouping from clustering stage.

| Field | Type | Notes |
|-------|------|-------|
| `theme` | `str` | Cluster label |
| `summary` | `str` | Brief theme description |
| `paper_ids` | `list[str]` | Member `paper_id` values |

### PaperExtraction

Per-paper structured extraction (synthesis Pass A). Stored as artifact `paper_extractions`.

| Field | Type |
|-------|------|
| `paper_id`, `title` | identifiers |
| `methodology`, `datasets`, `benchmarks`, `limitations`, `findings` | `list[str]` |

### PaperAnalysis

Per-paper analysis in the final report.

| Field | Type |
|-------|------|
| `paper_id`, `title`, `year`, `venue`, `url`, `doi` | metadata |
| `key_points`, `why_relevant` | `list[str]` |

### SynthesisResult

Cross-paper synthesis (Pass B).

| Field | Type |
|-------|------|
| `agreements`, `disagreements`, `trends`, `gaps` | `list[str]` |
| `datasets`, `methodologies` | `list[str]` |

### GapAnalysisResult

Prioritized research gaps and opportunities.

| Field | Type |
|-------|------|
| `gaps`, `opportunities`, `underexplored_areas` | `list[str]` |

### EnhancedResearchReport

Final pipeline output — the primary deliverable.

| Field | Type | Notes |
|-------|------|-------|
| `query` | `str` | Original user query |
| `executive_summary` | `str` | High-level overview |
| `papers` | `list[PaperAnalysis]` | Per-paper analyses |
| `clusters` | `list[PaperCluster]` | Thematic groupings |
| `synthesis` | `Optional[SynthesisResult]` | Cross-paper synthesis |
| `gap_analysis` | `Optional[GapAnalysisResult]` | Gap/opportunity analysis |
| `gaps` | `list[str]` | Flat gap list (legacy convenience) |
| `timeline` | `list[str]` | Chronological trend lines |
| `citation_index` | `dict[str, str]` | Citation key → paper ID |
| `exports` | `dict[str, str]` | BibTeX, CSL, etc. |

`to_research_report()` converts to the legacy `ResearchReport` shape used by some renderers.

## Pipeline result wrapper

`ResearchPipelineResult` (`src/core/pipeline.py`) wraps the full run:

| Field | Purpose |
|-------|---------|
| `query` | Original query |
| `output` | Final stage output (`EnhancedResearchReport`) |
| `session_id` | Research session UUID |
| `stage_results` | Per-stage duration, warnings, metrics |
| `warnings` | Accumulated pipeline warnings |
| `partial` | `true` if any stage returned partial/heuristic output |
| `duration_ms` | Total wall time |
| `metrics` | Aggregated pipeline metrics |
| `artifacts` | Subset of artifact store exported to callers |

Exported artifact keys: `ranked_papers`, `retrieved_papers`, `paper_analyses`, `paper_clusters`, `synthesis_result`, `gap_analysis`, `citation_exports`, `citation_index`, `enhanced_report`.

## Session and context types

**`ResearchSession`** (`src/core/context.py`) — in-memory session with UUID, timestamps, and optional `context_json` for interactive follow-ups.

**`PipelineContext`** — shared state per run: query, resolved config, session, metrics, warnings, stage results, and the artifact dictionary.

**`StageResult[T]`** — generic stage output wrapper with `output`, `duration_ms`, `metrics`, `warnings`, and `partial` flag.

## Related pages

- [Artifacts](artifacts.md) — which types are stored as artifacts vs passed on the data chain
- [Pipeline stages](pipeline-stages.md) — stage index
- [Output formats](../user-guide/output-formats.md) — how `EnhancedResearchReport` is rendered
