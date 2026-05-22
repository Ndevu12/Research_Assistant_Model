# Artifact Registry

Pipeline stages communicate through two mechanisms:

1. **Sequential `data` chain** — each stage's output becomes the next stage's input.
2. **Shared artifact store** — `PipelineContext.set_artifact()` / `get_artifact()` for cross-stage data that does not fit the linear chain.

Source: `src/core/context.py`, `src/core/pipeline.py`, stage modules under `src/research/`, `src/retrieval/`, `src/analysis/`, `src/reporting/`.

## Master artifact map

| Artifact key | Type | Set by | Read by |
|--------------|------|--------|---------|
| `query_understanding` | `QueryUnderstandingResult` | query_understanding | relevance_scoring |
| `expanded_queries` | `ExpandedQuerySet` | query_expansion | — |
| `cached_papers` | `list[dict]` | orchestrator (`initial_artifacts`) | retrieval |
| `retrieved_papers` | `list[RetrievedPaper]` | retrieval | synthesis (recovery) |
| `deduplication_stats` | `dict[str, int]` | deduplication | — |
| `query_embedding` | `list[float]` | ranking | relevance_scoring, clustering |
| `paper_embeddings` | `dict[str, list[float]]` | ranking | relevance_scoring, clustering |
| `ranked_papers` | `list[RankedPaper]` | ranking, relevance_scoring, synthesis | synthesis, citation_export, report_generation |
| `relevance_filter_reasons` | `dict[str, str]` | relevance_scoring | — |
| `paper_clusters` | `list[PaperCluster]` | clustering | synthesis, gap_analysis, report_generation |
| `paper_extractions` | `list[PaperExtraction]` | synthesis | synthesis (recovery) |
| `paper_analyses` | `list[PaperAnalysis]` | synthesis | report_generation |
| `synthesis_result` | `SynthesisResult` | synthesis | gap_analysis, report_generation |
| `gap_analysis` | `GapAnalysisResult` | gap_analysis | report_generation |
| `citation_exports` | `dict[str, str]` | citation_export | report_generation (via `data` param) |
| `citation_index` | `dict[str, str]` | citation_export | report_generation |
| `enhanced_report` | `EnhancedResearchReport` | report_generation | pipeline result, API, CLI |

## Exported artifacts

`ResearchPipeline.execute()` exports a subset of artifacts in `ResearchPipelineResult.artifacts`:

```
ranked_papers, retrieved_papers, paper_analyses, paper_clusters,
synthesis_result, gap_analysis, citation_exports, citation_index, enhanced_report
```

Internal-only artifacts (`query_understanding`, embeddings, `deduplication_stats`, etc.) are available in debug dumps when `debug_enabled` is set.

## Pre-populated artifacts

### Session cache bypass

When memory caching is enabled and a cache hit occurs, `run_research_with_result()` in `src/retrieval/orchestrator.py` pre-populates:

```python
initial_artifacts = {"cached_papers": cache_hit_papers}
```

The retrieval stage detects `cached_papers`, skips provider calls, and sets `retrieved_papers` directly.

## Embedding artifacts

Ranking stage stores embeddings via `store_ranking_embedding_result()` in `src/research/embedding_context.py`:

- `query_embedding` — embedding vector for the user query
- `paper_embeddings` — map of `paper_id` → embedding vector

These are consumed by relevance_scoring (adaptive embedding floor) and clustering (HDBSCAN input), avoiding redundant embedding computation.

## Artifact vs data chain

Some values exist in **both** places by design:

| Value | On data chain | In artifacts |
|-------|---------------|--------------|
| Ranked papers | Passed through relevance_scoring → clustering | Also stored/updated as `ranked_papers` |
| Synthesis | Passed to gap_analysis | Also stored as `synthesis_result` |
| Citation exports | Passed to report_generation | Also stored as `citation_exports` |

Downstream stages that need data from earlier stages (e.g., report_generation reading `paper_clusters` while receiving citation exports on the chain) rely on the artifact store.

## Debug visibility

When `RA_PIPELINE__DEBUG=true` (or `debug_enabled` in config), the pipeline writes `logs/debug/pipeline_{session_id}_{timestamp}.json` containing:

- Stage result summaries (duration, warnings, partial flags)
- Artifact **key names** (not full values — values are listed by key only in `to_debug_dict()`)
- Pipeline metrics

See [Logging and debug](../operations/logging-and-debug.md).

## Related pages

- [Pipeline stages](pipeline-stages.md) — stage index with artifact columns
- [Data model](data-model.md) — Pydantic type definitions
- Per-stage artifact details in [Stage deep dives](stages/query-understanding.md)
