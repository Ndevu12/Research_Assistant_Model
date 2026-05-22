# Pipeline Stages

The research pipeline runs eleven stages in fixed order. Each stage implements the `PipelineStage` protocol (`name` + `async run(ctx, data) → StageResult`).

Built by `build_pipeline()` in `src/retrieval/orchestrator.py`. Registry keys in `src/core/registry.py`.

## Stage order

```
query_understanding → query_expansion → retrieval → deduplication → ranking →
relevance_scoring → clustering → synthesis → gap_analysis → citation_export → report_generation
```

## Summary table

| # | Stage | Class | LLM | Timeout | Deep dive |
|---|-------|-------|-----|---------|-----------|
| 1 | query_understanding | `QueryUnderstandingStage` | No | 300 s | [→](stages/query-understanding.md) |
| 2 | query_expansion | `QueryExpansionStage` | Optional | 300 s | [→](stages/query-expansion.md) |
| 3 | retrieval | `RetrievalStage` | No | 300 s | [→](stages/retrieval.md) |
| 4 | deduplication | `DeduplicationStage` | No | 300 s | [→](stages/deduplication.md) |
| 5 | ranking | `RankingStage` | No | 300 s | [→](stages/ranking.md) |
| 6 | relevance_scoring | `RelevanceScoringStage` | No | 300 s | [→](stages/relevance-scoring.md) |
| 7 | clustering | `ClusteringStage` | No | 300 s | [→](stages/clustering.md) |
| 8 | synthesis | `SynthesisStage` | Optional (two-pass) | **600 s** | [→](stages/synthesis.md) |
| 9 | gap_analysis | `GapAnalysisStage` | Optional | 300 s | [→](stages/gap-analysis.md) |
| 10 | citation_export | `CitationExportStage` | No | 300 s | [→](stages/citation-export.md) |
| 11 | report_generation | `ReportGenerationStage` | No | 300 s | [→](stages/report-generation.md) |

Default timeouts from `pipeline.stage_timeout_seconds` (300) and `pipeline.synthesis_timeout_seconds` (600).

## Enable/disable

Each stage can be toggled via `pipeline.enabled_stages.{stage_name}` in YAML or environment. Disabled stages are skipped; downstream stages receive the last enabled stage's output unchanged. See [Stage toggles](../configuration/stage-toggles.md).

## Execution behavior

| Mechanism | Behavior |
|-----------|----------|
| Sequential `data` chain | Each stage output → next stage input |
| Artifact store | Cross-stage shared state on `PipelineContext` |
| LLM resolution | `resolve_effective_settings()` before first stage |
| Failure handling | `continue_on_stage_failure: true` (default) — heuristic recovery |
| Timeout recovery | `src/core/stage_recovery.py` — synthesis and gap_analysis have dedicated fallbacks |
| Progress events | `PipelineEventBus` emits stage start/complete for stderr progress reporter |

## Stage recovery

| Stage | Recovery on timeout/failure |
|-------|----------------------------|
| synthesis | Heuristic extraction + synthesis from ranked papers |
| gap_analysis | Heuristic gaps from synthesis fields + clusters |
| All others | Return prior `data` unchanged |

## Data-flow diagram

```mermaid
flowchart LR
  Q[query: str] --> QU[query_understanding]
  QU -->|QueryUnderstandingResult| QE[query_expansion]
  QE -->|ExpandedQuerySet| RT[retrieval]
  RT -->|list RetrievedPaper| DD[deduplication]
  DD -->|list RetrievedPaper| RK[ranking]
  RK -->|list RankedPaper| RS[relevance_scoring]
  RS -->|list RankedPaper| CL[clustering]
  CL -->|list PaperCluster| SY[synthesis]
  SY -->|SynthesisResult| GA[gap_analysis]
  GA -->|GapAnalysisResult| CE[citation_export]
  CE -->|dict exports| RG[report_generation]
  RG -->|EnhancedResearchReport| OUT[output]
```

## Config keys by stage

| Stage | Primary config sections |
|-------|------------------------|
| query_understanding | — |
| query_expansion | `query_expansion.*` |
| retrieval | `retrieval.*`, `retrieval.providers.*` |
| deduplication | `deduplication.*`, `embedding.*` |
| ranking | `ranking.*`, `embedding.*` |
| relevance_scoring | `relevance_scoring.*` |
| clustering | `clustering.*`, `embedding.*`, `ranking.*` |
| synthesis | `synthesis.*`, `llm.*` |
| gap_analysis | `synthesis.llm_enabled` (gates LLM — no separate gap flag) |
| citation_export | — |
| report_generation | `relevance_scoring.*` (executive summary embedding floor) |

## Related pages

- [Architecture overview](overview.md)
- [Artifacts](artifacts.md)
- [Data model](data-model.md)
- [LLM layer](llm-layer.md)
- [Stage toggles](../configuration/stage-toggles.md)
