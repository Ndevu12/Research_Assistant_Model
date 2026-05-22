# Phase 0 — Code Analysis Artifacts

Internal reference produced from source and test analysis. **Not published** in the MkDocs site nav — use these artifacts when writing user-facing pages in Phase 1+.

| Artifact | Purpose | Primary consumers |
|----------|---------|-------------------|
| [artifact-registry.md](artifact-registry.md) | Pipeline stage I/O, artifacts, config keys, LLM usage | `architecture/pipeline-stages.md`, `architecture/overview.md`, `configuration/stage-toggles.md` |
| [config-inventory.md](config-inventory.md) | `AppSettings` fields, YAML files, env vars, precedence | `configuration/*`, `getting-started/*` |
| [test-behavior-index.md](test-behavior-index.md) | Test map, mocks, coverage gaps | `development/testing.md` |
| [provider-http-matrix.md](provider-http-matrix.md) | Retrieval provider HTTP details, CLI vs pipeline | `retrieval/*`, `operations/troubleshooting.md` |
| [llm-resolution-tree.md](llm-resolution-tree.md) | LLM provider/model/feature resolution | `llm/*`, `architecture/llm-layer.md` |

**Generated:** 2026-05-22  
**Source revision:** analyzed against current `main` tree (`src/`, `config/`, `tests/`).

## Key findings (executive summary)

1. **11 pipeline stages** share artifacts via `PipelineContext`; final `ResearchPipelineResult.artifacts` exports a subset (see artifact registry).
2. **CLI shortcut** (`run_research_helper`) hardcodes OpenAlex + Semantic Scholar — differs from full pipeline/API.
3. **Heuristic LLM defaults** (`synthesis.llm_enabled: false`, `query_expansion.llm_enabled: false`) resolved at pipeline start via `resolve_effective_settings()`.
4. **3 retrieval stubs** (PubMed, CORE, DBLP) raise `NotImplementedError` if enabled.
5. **Config precedence:** constructor kwargs > process env > `.env` > merged YAML > field defaults; plus post-load LLM feature resolution.
6. **Doc/code gaps to fix in Phase 1:** `llm.timeout_seconds` and `llm.temperature` unused; per-provider `limit` ignored by `RetrievalStage`; `.env.example` enables `RA_DEBUG=1` while `RA_PIPELINE__DEBUG=false`.
