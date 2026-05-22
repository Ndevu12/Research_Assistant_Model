# Artifact Registry — Pipeline Stages

Source: `src/core/pipeline.py`, `src/core/registry.py`, `src/retrieval/orchestrator.py`, stage modules under `src/research/`, `src/retrieval/`, `src/analysis/`, `src/reporting/`.

## Stage order

```
query_understanding → query_expansion → retrieval → deduplication → ranking →
relevance_scoring → clustering → synthesis → gap_analysis → citation_export → report_generation
```

Built by `build_pipeline()` in `src/retrieval/orchestrator.py:37–50`. Registry keys in `src/core/registry.py:136–148`.

## Execution model

| Mechanism | Location | Behavior |
|-----------|----------|----------|
| Sequential `data` chain | `pipeline.py:148` | Each stage output becomes next stage input |
| Shared artifact store | `context.py` | `ctx.get_artifact` / `ctx.set_artifact` |
| Stage enable gate | `pipeline.py` + `settings.pipeline.enabled_stages` | Disabled stages skipped |
| Timeouts | `pipeline.py:66–69` | Default `stage_timeout_seconds` (300s); synthesis uses `synthesis_timeout_seconds` (600s) |
| LLM resolution | `pipeline.py:130` | `resolve_effective_settings()` before stages run |
| Failure handling | `continue_on_stage_failure` | Default `True`; partial results + warnings |
| Debug dump | `pipeline.py:154–155` | When `debug_enabled`, writes `logs/debug/pipeline_*.json` |

## Master artifact map

| Artifact key | Set by | Read by |
|--------------|--------|---------|
| `query_understanding` | query_understanding | relevance_scoring |
| `expanded_queries` | query_expansion | — |
| `cached_papers` | orchestrator (`initial_artifacts`) | retrieval |
| `retrieved_papers` | retrieval | synthesis (recovery) |
| `deduplication_stats` | deduplication | — |
| `query_embedding` | ranking (`embedding_context.py`) | relevance_scoring, clustering |
| `paper_embeddings` | ranking (`embedding_context.py`) | relevance_scoring, clustering |
| `ranked_papers` | ranking, relevance_scoring, synthesis | synthesis, citation_export, report_generation |
| `relevance_filter_reasons` | relevance_scoring | — |
| `paper_clusters` | clustering | synthesis, gap_analysis, report_generation |
| `paper_extractions` | synthesis | synthesis (recovery) |
| `paper_analyses` | synthesis | report_generation |
| `synthesis_result` | synthesis | gap_analysis, report_generation |
| `gap_analysis` | gap_analysis | report_generation |
| `citation_exports` | citation_export | report_generation (via `data` param) |
| `citation_index` | citation_export | report_generation |
| `enhanced_report` | report_generation | pipeline result, API, CLI |

**Exported in `ResearchPipelineResult.artifacts`** (`pipeline.py:167–182`):  
`ranked_papers`, `retrieved_papers`, `paper_analyses`, `paper_clusters`, `synthesis_result`, `gap_analysis`, `citation_exports`, `citation_index`, `enhanced_report`.

---

## Per-stage reference

### 1. `query_understanding`

| Field | Value |
|-------|-------|
| Class | `QueryUnderstandingStage` |
| File | `src/research/query_understanding.py` |
| Input (`data`) | `str` — raw query |
| Input artifacts | None |
| Output artifacts | `query_understanding` → `QueryUnderstandingResult` |
| `StageResult` type | `StageResult[QueryUnderstandingResult]` |
| Config keys | None |
| LLM | No — regex/heuristic |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 2. `query_expansion`

| Field | Value |
|-------|-------|
| Class | `QueryExpansionStage` |
| File | `src/research/query_expansion.py` |
| Input (`data`) | `str \| QueryUnderstandingResult` |
| Input artifacts | None |
| Output artifacts | `expanded_queries` → `ExpandedQuerySet` |
| `StageResult` type | `StageResult[ExpandedQuerySet]` |
| Config keys | `query_expansion.llm_enabled`, `llm_mode`, `max_variants`, `max_sub_questions` |
| LLM | Optional — `AgentRole.EXPANSION` when `query_expansion.llm_enabled`; heuristics always run first |
| Timeout | `pipeline.stage_timeout_seconds` |

**Note:** `expand_query_llm` uses `get_settings().llm`, not `ctx.config.llm` — potential inconsistency if settings differ.

---

### 3. `retrieval`

| Field | Value |
|-------|-------|
| Class | `RetrievalStage` |
| File | `src/retrieval/retrieval_stage.py` |
| Input (`data`) | `ExpandedQuerySet` |
| Input artifacts | `cached_papers` (session cache bypass) |
| Output artifacts | `retrieved_papers` → `list[RetrievedPaper]` |
| `StageResult` type | `StageResult[list[RetrievedPaper]]` |
| Config keys | `retrieval.concurrency_limit`, `retrieval.per_provider_limit`, `retrieval.providers.{name}.enabled` |
| LLM | No |
| Timeout | `pipeline.stage_timeout_seconds` |

**Limit caveat:** Stage always passes `settings.retrieval.per_provider_limit` to `provider.search()` — per-provider `limit` in YAML is ignored.

---

### 4. `deduplication`

| Field | Value |
|-------|-------|
| Class | `DeduplicationStage` |
| File | `src/retrieval/deduplication.py` |
| Input (`data`) | `list[RetrievedPaper]` |
| Output artifacts | `deduplication_stats` → `dict[str, int]` |
| Config keys | `deduplication.enabled`, `enable_embedding_dedup`, `embedding_similarity_threshold`; `embedding.*` when embedding dedup runs |
| LLM | No — metadata union-find + optional embedding similarity |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 5. `ranking`

| Field | Value |
|-------|-------|
| Class | `RankingStage` |
| File | `src/research/ranking.py` |
| Input (`data`) | `list[RetrievedPaper]` |
| Output artifacts | `ranked_papers`; `query_embedding`; `paper_embeddings` |
| Config keys | `ranking.top_k`, `ranking.weights.*`, `domain_penalty_multiplier`, `outlier_embedding_gap`, `keyword_collision_max_sim`, `canonical_boost`; `embedding.*` |
| LLM | No |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 6. `relevance_scoring`

| Field | Value |
|-------|-------|
| Class | `RelevanceScoringStage` |
| File | `src/research/relevance_scoring.py` |
| Input (`data`) | `list[RankedPaper]` |
| Input artifacts | `query_understanding`, `query_embedding`, `paper_embeddings` |
| Output artifacts | `ranked_papers` (filtered); `relevance_filter_reasons` |
| Config keys | `relevance_scoring.*` (min scores, adaptive floor, concept matching) |
| LLM | No |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 7. `clustering`

| Field | Value |
|-------|-------|
| Class | `ClusteringStage` |
| File | `src/research/clustering.py` |
| Input (`data`) | `list[RankedPaper]` |
| Input artifacts | `paper_embeddings` |
| Output artifacts | `paper_clusters` → `list[PaperCluster]` |
| Config keys | `clustering.*`; `embedding.*`; `ranking.*` (adapter) |
| LLM | No — HDBSCAN + keyword fallback |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 8. `synthesis`

| Field | Value |
|-------|-------|
| Class | `SynthesisStage` |
| File | `src/analysis/synthesis.py` |
| Input (`data`) | `list[PaperCluster]` |
| Input artifacts | `ranked_papers`; fallback `retrieved_papers` |
| Output artifacts | `paper_extractions`, `paper_analyses`, `synthesis_result`; may refresh `ranked_papers` on recovery |
| Config keys | `synthesis.llm_enabled`, `llm_mode`, `max_llm_papers`, retries, `concurrency`, `circuit_breaker_failures`; `llm.*` |
| LLM | Two-pass when enabled: `AgentRole.EXTRACTION` (per paper, capped) → `AgentRole.SYNTHESIS` (collective). Heuristic fallback when disabled or on failure. |
| Timeout | **`pipeline.synthesis_timeout_seconds`** (600s) |

**Recovery:** `src/core/stage_recovery.py` — synthesis timeout returns heuristic partial output.

---

### 9. `gap_analysis`

| Field | Value |
|-------|-------|
| Class | `GapAnalysisStage` |
| File | `src/analysis/gap_analysis.py` |
| Input (`data`) | `SynthesisResult` (may be wrong type; recovered) |
| Input artifacts | `paper_clusters`; `synthesis_result` |
| Output artifacts | `gap_analysis` → `GapAnalysisResult` |
| Config keys | **`synthesis.llm_enabled`** gates LLM (no separate gap flag) |
| LLM | Optional — `AgentRole.GAP_ANALYSIS` when `synthesis.llm_enabled`; else `_heuristic_gap_analysis` |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 10. `citation_export`

| Field | Value |
|-------|-------|
| Class | `CitationExportStage` |
| File | `src/reporting/citations.py` |
| Input (`data`) | `GapAnalysisResult` (passed through) |
| Input artifacts | `ranked_papers` |
| Output artifacts | `citation_exports`, `citation_index` |
| Config keys | None |
| LLM | No — BibTeX/CSL via `generate_citation_exports` |
| Timeout | `pipeline.stage_timeout_seconds` |

---

### 11. `report_generation`

| Field | Value |
|-------|-------|
| Class | `ReportGenerationStage` |
| File | `src/reporting/report_generation.py` |
| Input (`data`) | `dict[str, str]` — citation exports |
| Input artifacts | `synthesis_result`, `gap_analysis`, `paper_clusters`, `paper_analyses`, `ranked_papers`, `citation_index` |
| Output artifacts | `enhanced_report` → `EnhancedResearchReport` |
| Config keys | `relevance_scoring.*` (executive summary embedding floor) |
| LLM | No — deterministic assembly |
| Timeout | `pipeline.stage_timeout_seconds` |

---

## Stage recovery (`src/core/stage_recovery.py`)

| Stage | Recovery behavior |
|-------|-------------------|
| `synthesis` | Heuristic extraction/synthesis from ranked papers |
| `gap_analysis` | `recover_gap_analysis_output()` — heuristic from synthesis + clusters |
| Others | Return prior `data` unchanged |

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

## Non-pipeline LLM module

`src/analysis/llm.py` creates a module-level `analysis_agent` at import via `AgentFactory()` — **not** part of the 11-stage pipeline. Used by legacy/orchestrator helper paths.
