# Stage: gap_analysis

Expands synthesis gaps into prioritized research opportunities and underexplored areas.

| | |
|---|---|
| **Class** | `GapAnalysisStage` |
| **Module** | `src/analysis/gap_analysis.py` |
| **Registry key** | `gap_analysis` |

## Input / output

| Direction | Type | Details |
|-----------|------|---------|
| Input (`data`) | `SynthesisResult` | From synthesis (may be wrong type — recovered) |
| Input (artifacts) | `paper_clusters`, `synthesis_result` | Context for gap identification |
| Output (`data`) | `GapAnalysisResult` | Passed to citation_export |
| Artifacts written | `gap_analysis` | Read by report_generation |

## Behavior

### Heuristic mode (when `synthesis.llm_enabled` is false)

Derives gaps from synthesis fields (`gaps`, `trends`, `disagreements`) and cluster themes. No LLM call. Adds warning: *"Skipped LLM gap analysis (synthesis.llm_enabled=false)"*.

### LLM mode

Calls `AgentRole.GAP_ANALYSIS` with structured JSON response containing gaps, opportunities, and underexplored areas.

!!! info "LLM gate"
    Gap analysis LLM is controlled by **`synthesis.llm_enabled`**, not a separate gap-analysis config flag.

### Input recovery

`resolve_synthesis_input()` recovers synthesis from artifacts if the data chain carries an unexpected type (e.g., cluster list from a skipped synthesis stage).

## Configuration

| Key | Purpose |
|-----|---------|
| `synthesis.llm_enabled` | Gates LLM gap analysis |
| `llm.*` | Provider/model when LLM enabled |

## LLM

Optional — `AgentRole.GAP_ANALYSIS` when `synthesis.llm_enabled`. Heuristic fallback otherwise.

## Timeout

`pipeline.stage_timeout_seconds` (default 300 s).

## Recovery

`recover_gap_analysis_output()` in `src/core/stage_recovery.py` on pipeline timeout. In-stage heuristic fallback on LLM exception.

## Metrics

- `gap_count`
- `opportunity_count`

## Related

- [Previous: synthesis](synthesis.md)
- [Next: citation_export](citation-export.md)
- [Data model: GapAnalysisResult](../data-model.md)
