# Stage Toggles

Each pipeline stage can be disabled via `pipeline.enabled_stages` in YAML or matching `RA_PIPELINE__ENABLED_STAGES__*` environment variables.

Source: `PipelineConfig.enabled_stages` in `src/config/settings.py`; checked in `ResearchPipeline._is_stage_enabled()`.

## All stages (default: enabled)

| Stage key | Human label | Typical output |
|-----------|-------------|----------------|
| `query_understanding` | Understanding your question | Parsed intent, concepts, sub-questions |
| `query_expansion` | Expanding search queries | Additional search variants |
| `retrieval` | Retrieving papers | `RetrievedPaper` list from scholarly APIs |
| `deduplication` | Removing duplicates | Deduplicated paper set |
| `ranking` | Ranking papers | `RankedPaper` list (top-k) |
| `relevance_scoring` | Scoring semantic relevance | Filtered ranked papers |
| `clustering` | Grouping by theme | `PaperCluster` groups |
| `synthesis` | Synthesizing insights | Cross-paper themes and analyses |
| `gap_analysis` | Identifying research gaps | Gap findings |
| `citation_export` | Formatting citations | BibTeX/APA/MLA/Chicago strings |
| `report_generation` | Organizing final report | `EnhancedResearchReport` |

Stage deep dives: [Pipeline stages](../architecture/pipeline-stages.md).

## YAML configuration

```yaml
pipeline:
  enabled_stages:
    query_understanding: true
    query_expansion: true
    retrieval: true
    deduplication: true
    ranking: true
    relevance_scoring: true
    clustering: true
    synthesis: true
    gap_analysis: true
    citation_export: true
    report_generation: true
```

**Disable clustering** (faster runs, flat paper list in report):

```yaml
pipeline:
  enabled_stages:
    clustering: false
```

**Retrieval-only smoke test** (skip analysis and reporting):

```yaml
pipeline:
  enabled_stages:
    synthesis: false
    gap_analysis: false
    citation_export: false
    report_generation: false
```

!!! warning "Downstream dependencies"
    Disabling early stages (e.g. `retrieval`) causes later stages to receive empty or stale data. Recovery heuristics may produce partial reports. Prefer disabling analysis stages for quick retrieval tests.

## Environment overrides

Nested env keys mirror YAML:

```bash
RA_PIPELINE__ENABLED_STAGES__CLUSTERING=false
RA_PIPELINE__ENABLED_STAGES__GAP_ANALYSIS=false
```

Disable multiple stages by setting each key independently.

## Related pipeline settings

These are **not** stage toggles but affect stage behavior:

| Setting | Default | Effect |
|---------|---------|--------|
| `pipeline.continue_on_stage_failure` | `true` | On failure/timeout, run heuristic recovery instead of aborting |
| `pipeline.stage_timeout_seconds` | `300` | Timeout for all stages except synthesis |
| `pipeline.synthesis_timeout_seconds` | `600` | Synthesis-specific timeout |
| `deduplication.enabled` | `true` | Dedup logic within the deduplication stage |

When a stage times out or fails with `continue_on_stage_failure=true`, `recover_stage_output()` supplies fallback data and the run is marked **partial**. Progress output shows a ⚠ icon for partial stages.

## Timeouts vs toggles

Disabling a stage skips it entirely — no timeout applies. Enabled stages respect:

- **Synthesis:** `synthesis_timeout_seconds` (default 600s)
- **All others:** `stage_timeout_seconds` (default 300s)

Set timeout to `0` to disable the asyncio wait (unlimited; not recommended for retrieval).

See also: [Configuration precedence](precedence.md), [Logging and debug](../operations/logging-and-debug.md), [Progress streaming](../operations/progress-streaming.md).
