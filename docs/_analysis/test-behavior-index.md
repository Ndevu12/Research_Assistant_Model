# Test Behavior Index

Source: all 28 files matching `tests/test_*.py`. Internal reference for `docs/development/testing.md`.

## Summary by domain

| Domain | Test files |
|--------|------------|
| Config / LLM resolution | `test_config_settings.py`, `test_resolve_llm_features.py`, `test_model_selection.py` |
| Pipeline core | `test_pipeline_core.py`, `test_paper_adapters.py`, `test_phase3_extensibility.py` |
| Research stages | `test_research_stages.py`, `test_retrieval_stage.py`, `test_synthesis.py`, `test_research_quality.py` |
| Retrieval providers | `test_providers.py` |
| Embeddings | `test_embeddings.py` |
| Reporting / export | `test_reporting.py`, `test_export.py` |
| LLM layer | `test_llm_providers.py`, `test_graceful_response_handling.py` |
| Orchestrator / degradation | `test_json_parsing_bug_exploration.py`, `test_json_parsing_preservation.py` |
| CLI / interactive | `test_main_mode_detection.py`, `test_interactive_mode.py`, `test_complete_workflow.py`, `test_input_handler.py`, `test_message_formatting.py`, `test_signal_handling.py`, `test_interactive_filters.py` |
| Memory | `test_memory.py` |
| Models | `test_models.py` |
| Progress | `test_progress_reporter.py` |

---

## Per-file index

### `test_config_settings.py`

| | |
|---|---|
| **Modules** | `src.config.settings` |
| **Fixtures** | `temp_config_dir` — tmp YAML overlays |
| **Mocks** | `monkeypatch` for `RA_*` env |

| Test | Behavior |
|------|----------|
| `test_merges_default_and_overlay_files` | YAML merge: overlay wins |
| `test_loads_from_yaml` | `AppSettings.from_yaml` |
| `test_env_overrides_yaml` | `RA_LLM__MODEL`, `RA_RANKING__TOP_K` override YAML |
| `test_constructor_overrides_env_and_yaml` | Init kwargs beat env |
| `test_debug_enabled_from_env` | `RA_DEBUG=1` → `debug_enabled` |
| `test_retrieval_providers_defaults` | OpenAlex enabled by default |

---

### `test_resolve_llm_features.py`

| | |
|---|---|
| **Modules** | `src.config.resolve_llm_features` |
| **Fixtures** | `catalog_dir` — Ollama catalog with 8B/3B models |

| Test | Behavior |
|------|----------|
| `test_llm_mode_auto_8b` | Auto + 8B → LLM on, `max_llm_papers=5` |
| `test_llm_mode_auto_3b` | Auto + 3B → LLM off |
| `test_llm_mode_on_off` | Explicit on/off overrides catalog |
| `test_env_llm_enabled_overrides_mode` | Env bool overrides `llm_mode: off` |
| `test_cloud_provider_auto_enables_llm` | OpenAI auto-enables LLM |
| `test_auto_resolves_model_name` | End-to-end auto resolution |

---

### `test_model_selection.py`

| | |
|---|---|
| **Modules** | `src.config.model_selection` |
| **Fixtures** | `catalog_dir` |

| Class | Behavior |
|-------|----------|
| `TestModelCatalog` | Catalog load, case-insensitive lookup |
| `TestModelSelection` | RAM-based selection, fallback, swap pressure, explicit/env resolution |
| `TestOllamaListParsing` | `ollama list` stdout parsing |

---

### `test_embeddings.py`

| | |
|---|---|
| **Modules** | `src.embeddings.cache`, `src.embeddings.sentence_transformers` |
| **Mocks** | `patch.object(provider, "_load_model")`, `MagicMock` encode |

| Class | Behavior |
|-------|----------|
| `TestEmbeddingCache` | Disk cache round-trip, model-specific keys, batch hit/miss |
| `TestSentenceTransformerEmbeddingProvider` | Cache reuse, cosine similarity, empty input shape |

---

### `test_models.py`

| | |
|---|---|
| **Modules** | `src.retrieval.models` |

| Class | Behavior |
|-------|----------|
| `TestRetrievedPaper` | Legacy `source`/`provider`/`paper_id` aliases |
| `TestPipelineModels` | Pydantic defaults for pipeline models |
| `TestEnhancedResearchReport` | `to_research_report` adapter |

---

### `test_pipeline_core.py`

| | |
|---|---|
| **Modules** | `src.core.pipeline`, `src.core.context`, `src.core.metrics` |
| **Fixtures** | `EchoStage`, `FailingStage`, `PartialStage` stubs |

| Test | Behavior |
|------|----------|
| `test_pipeline_runs_stages_in_order` | Single stage passes query |
| `test_pipeline_continues_after_stage_failure` | `continue_on_stage_failure=True` |
| `test_pipeline_skips_disabled_stages` | `enabled_stages` gate |
| `test_pipeline_records_partial_stage` | Stage `partial=True` → warnings |
| `test_pipeline_isolates_stages_and_preserves_order` | A→B→C chaining |
| `test_pipeline_propagates_partial_from_multiple_stages` | Multiple partial warnings |
| `test_pipeline_metrics_emit_and_finalize` | Metrics for stages/retrieval/ranking/clustering/LLM |

---

### `test_paper_adapters.py`

| | |
|---|---|
| **Modules** | `src.core.paper_adapters` |

| Test | Behavior |
|------|----------|
| `test_ensure_ranked_papers_from_retrieved` | Retrieved → ranked conversion + warnings |
| `test_ensure_ranked_papers_passthrough` | Already-ranked unchanged |

---

### `test_research_stages.py`

| | |
|---|---|
| **Modules** | query_expansion, ranking, relevance_scoring, clustering, deduplication, pipeline |
| **Fixtures** | `MockEmbeddingProvider`, `FixedEmbeddingProvider`, `_paper()` |
| **Mocks** | `monkeypatch` HDBSCAN; `RetrievalStub` |

| Class | Scope |
|-------|-------|
| `TestQueryExpansion` | Heuristic expansion, stability, metrics |
| `TestRanking` | Ordering, determinism, penalties, canonical boost, embeddings |
| `TestRelevanceScoring` | Cached embeddings, `min_papers` floor, adaptive floor |
| `TestClustering` | HDBSCAN groups, noise→macro merge, singleton handling |
| `TestDeduplication` | DOI dedup, embedding near-dup, richer duplicate kept |
| `TestMetadataSanity` | Year/DOI correction, future year flags |
| `TestResearchPipelineStages` | End-to-end stub pipeline through clustering |

**Edge cases:** Homonym decoy papers; adaptive embedding floor; all-noise HDBSCAN → macro themes.

---

### `test_research_quality.py`

| | |
|---|---|
| **Modules** | query_expansion, ranking, relevance_scoring, clustering, report_generation |
| **Fixtures** | `DOMAIN_CASES` (NLP, biomedical, climate, economics); `FixedEmbeddingProvider` |

| Class | Behavior |
|-------|----------|
| `TestMultiDomainExpansion` | No degenerate variants across 4 domains |
| `TestMultiDomainRanking` | Embedding outlier demotes homonym decoys |
| `TestMultiDomainRelevance` | Adaptive filter drops decoy |
| `TestMultiDomainExecutiveSummary` | Summary excludes decoy terms |
| `TestNoDomainSpecificBranches` | No ML-specific branch constants in source |
| `TestMultiDomainClustering` | Noise merge → 1–4 macro themes |

---

### `test_retrieval_stage.py`

| | |
|---|---|
| **Modules** | `src.retrieval.retrieval_stage`, `src.core.pipeline` |
| **Fixtures** | `SuccessProvider`, `FailingProvider`, `EmptyProvider` |
| **Mocks** | `patch get_enabled_providers` |

| Test | Behavior |
|------|----------|
| `test_search_query_continues_when_one_provider_fails` | Partial success + warning |
| `test_search_query_returns_empty_when_all_providers_fail` | Empty + 2 warnings |
| `test_retrieve_papers_merges_successful_provider_results` | Multi-provider merge |
| `test_retrieval_stage_marks_partial_when_provider_fails` | `partial=True`, metrics |
| `test_retrieval_stage_not_partial_when_all_providers_succeed` | Full success |
| `test_pipeline_continues_after_retrieval_provider_failure` | Downstream runs after partial retrieval |

---

### `test_providers.py`

| | |
|---|---|
| **Modules** | `src.retrieval.providers` (OpenAlex, S2, arXiv, CrossRef) |
| **Mocks** | `patch` registry; `AsyncMock` aiohttp for health checks |

| Class | Behavior |
|-------|----------|
| `TestProviderRegistry` | Builtins registered; enabled/disabled filtering; `register_provider` |
| `test_search_enabled_providers_falls_back_when_one_provider_fails` | Cross-provider fallback |
| `test_health_check_enabled_providers_reports_status` | Healthy vs unhealthy |
| `test_arxiv/crossref_health_check_uses_lightweight_query` | Minimal health queries |
| `TestProviderNormalization` | Field mapping for all 4 live providers |

---

### `test_synthesis.py`

| | |
|---|---|
| **Modules** | `src.analysis.synthesis`, `src.analysis.gap_analysis`, `src.core.stage_recovery` |
| **Mocks** | `MagicMock(EnhancedResponseHandler)`; `patch create_llm_agent` |

| Class | Behavior |
|-------|----------|
| `TestSynthesisModels` | Pydantic schema validation |
| `TestHeuristicSynthesis` | Abstract extraction, aggregation, conflict detection |
| `TestSynthesisWorkflow` | LLM two-pass; heuristic fallback |
| `TestGapAnalysis` | LLM + heuristic gap analysis |
| `TestSynthesisPipelineStages` | Stage artifacts; mini-pipeline synthesis→gap |
| `TestStageRecovery` | Timeout recovery; `max_llm_papers` cap; skip LLM when disabled |

---

### `test_reporting.py`

| | |
|---|---|
| **Modules** | `src.reporting.*`, `src.retrieval.orchestrator` |
| **Mocks** | `patch run_research_with_result` |

| Class | Behavior |
|-------|----------|
| `TestMarkdownReporting` | Enhanced/legacy markdown, JSON/HTML, partial notice |
| `TestCitationExport` | Citation keys, BibTeX |
| `TestExecutiveSummary` | Template summary; embedding-gated findings |
| `TestReportGenerationStage` | Report assembly from artifacts |
| `TestOrchestratorFacade` | CLI prints enhanced report / no-results |

---

### `test_export.py`

| | |
|---|---|
| **Modules** | `src.export.{bibtex,apa,mla,chicago}` |

| Class | Behavior |
|-------|----------|
| `TestBibTeXExport`, `TestAPAExport`, `TestMLAExport`, `TestChicagoExport` | Style-specific formatting |
| `TestUnifiedExport` | `generate_citation_exports` aggregator |

---

### `test_llm_providers.py`

| | |
|---|---|
| **Modules** | `src.models.{ollama,openai,anthropic,factory}` |
| **Mocks** | `patch` OpenAI/Pydantic AI; `patch.dict` for missing keys |

| Class | Behavior |
|-------|----------|
| `TestNormalizeOpenAIBaseUrl` | Appends `/v1` |
| `TestLLMProviderRegistry` | Default Ollama; unknown → `KeyError` |
| `TestOllamaProvider`, `TestOpenAIProvider` | Endpoint wiring; API key required |
| `TestAgentFactory` | Role prompts; `create_llm_agent` compat |

---

### `test_memory.py`

| | |
|---|---|
| **Modules** | `src.memory.store` |
| **Fixtures** | `memory_store` (tmp SQLite) |

| Test | Behavior |
|------|----------|
| `test_create_and_load_session` | Session CRUD |
| `test_save_search_papers_and_report` | Search cache, papers, reports |
| `test_cache_key_is_stable` | Case-insensitive cache key |
| `test_update_session_context` | JSON context persistence |

---

### `test_progress_reporter.py`

| | |
|---|---|
| **Modules** | `src.utils.progress_reporter` |
| **Mocks** | `patch sys.stderr.isatty` |

| Test | Behavior |
|------|----------|
| `TestStageLabels` | Friendly labels |
| `TestProgressReporter` | Disabled → blocking; non-TTY disables reporter |

---

### `test_graceful_response_handling.py`

| | |
|---|---|
| **Modules** | `src.utils.{response_models,retry_manager,quality_monitor,enhanced_validation,content_quality,json_processing,model_adaptation,fallback_processing}` |

| Class | Behavior |
|-------|----------|
| `TestRetryManager` | Retry rules, prompt enhancement |
| `TestQualityMonitor` | Success/failure recording |
| `TestEnhancedValidation` | Retry strategy mapping |
| `TestContentQuality` | Empty/insufficient/incomplete analysis detection |
| `TestQueryAnalyzer` | Query broadening suggestions |
| `TestRelevanceScorer` | Paper relevance ordering |
| `TestJSONProcessing` | Extract, parse errors, validation |
| `TestModelAdaptation` | GPT/Claude detection, markdown stripping |
| `TestFallbackProcessing` | Unstructured text → structured fallback |

**Note:** Does not exercise `EnhancedResponseHandler` end-to-end.

---

### `test_json_parsing_bug_exploration.py`

| | |
|---|---|
| **Modules** | `src.retrieval.orchestrator.run_research_helper` |
| **Fixtures** | `tests.helpers.pipeline_mocks.mock_pipeline_result` |

| Class | Behavior |
|-------|----------|
| `TestJSONParsingBugCondition` | Malformed JSON still prints partial report |
| `TestScopedBugConditionProperty` | 12 parametrized malformed JSON cases |

---

### `test_json_parsing_preservation.py`

| | |
|---|---|
| **Modules** | `src.retrieval.orchestrator`, `src.utils.message_formatter` |

| Class | Behavior |
|-------|----------|
| `TestJSONParsingPreservation` | Valid JSON, code blocks, network/no-results messages |
| `TestPreservationProperties` | Parametrized valid JSON shapes |

---

### `test_main_mode_detection.py`

| | |
|---|---|
| **Modules** | `src.__main__.main` |
| **Mocks** | `patch sys.argv`, `asyncio.run`, helper functions |

| Class | Behavior |
|-------|----------|
| `TestMainModeDetection` | Query arg → batch; no arg → interactive |
| `TestModeDetectionEdgeCases` | `""` → interactive; `"   "` → batch |

---

### `test_interactive_mode.py`

| | |
|---|---|
| **Modules** | `src.__main__.run_interactive_mode` |
| **Mocks** | Session helpers, `get_user_query`, `builtins.input` |

| Test | Behavior |
|------|----------|
| Welcome/farewell | UX copy |
| Query loop | Separators, multi-query, KeyboardInterrupt |
| Integration | Full session flows |

---

### `test_complete_workflow.py`

| | |
|---|---|
| **Modules** | `src.__main__`, `src.utils.input_handler` |
| **Marks** | `@pytest.mark.slow` subprocess tests |

| Class | Behavior |
|-------|----------|
| `TestCompleteInteractiveWorkflow` | End-to-end interactive flows |
| `TestSystemLevelIntegration` | Real `python -m src` subprocess |

---

### `test_input_handler.py`

| | |
|---|---|
| **Modules** | `src.utils.input_handler` |

| Test | Behavior |
|------|----------|
| Empty/whitespace reprompt | Error + retry |
| exit/quit | Returns `None` |
| EOF | Returns `None` |

---

### `test_message_formatting.py`

| | |
|---|---|
| **Modules** | `src.utils.message_formatter` |

| Test | Behavior |
|------|----------|
| Prompt consistency | `query_prompt()` |
| Error prefix | `❌ Error:` |
| Separators | `-` * 60 between results |

---

### `test_signal_handling.py`

| | |
|---|---|
| **Modules** | `src.__main__.run_interactive_mode` |

| Test | Behavior |
|------|----------|
| Ctrl+C | Farewell, no traceback |
| Integration | Interrupt via `builtins.input` |

---

### `test_interactive_filters.py`

| | |
|---|---|
| **Modules** | `src.memory.filters` |

| Class | Behavior |
|-------|----------|
| `TestFollowUpParsing` | Year filters, focus, compare, export, new query |
| `TestPaperFiltering` | Year filter, keyword boost, report subset |

---

### `test_phase3_extensibility.py`

| | |
|---|---|
| **Modules** | registry, events, API scaffold, provider/fulltext stubs |

| Class | Behavior |
|-------|----------|
| `TestPhase3ProviderStubs` | PubMed/Core/DBLP registered, disabled, NIE |
| `TestFullTextScaffold` | PDF downloader & RAG index stubs |
| `TestPluginRegistry` | Bootstrap registers providers + stages |
| `TestPipelineEvents` | `StageEventCollector` fires start/complete |
| `TestPdfReadyHtml` | Print CSS, A4 `@page` |
| `TestApiScaffold` | FastAPI optional import |

---

## Cross-cutting patterns

| Pattern | Where used |
|---------|------------|
| Stub pipeline stages | `EchoStage`, `RetrievalStub`, `NamedEchoStage` |
| Provider stubs | `SuccessProvider` / `FailingProvider` |
| `mock_pipeline_result` | `tests/helpers/pipeline_mocks.py` |
| `FixedEmbeddingProvider` | Deterministic vectors for ranking/relevance/quality |
| `monkeypatch` HDBSCAN | Force all-noise labels |
| `capsys` | CLI output assertions |
| Parametrized multi-domain | `test_research_quality.py` |
| `@pytest.mark.slow` subprocess | `test_complete_workflow.py` |
| `@pytest.mark.asyncio` | Async stage/pipeline/memory tests |

---

## Coverage gaps (for docs)

| Gap | Detail |
|-----|--------|
| Query understanding | No dedicated unit test file |
| API routes | Only scaffold test in `test_phase3_extensibility.py` |
| `EnhancedResponseHandler` | Subcomponents tested, not end-to-end |
| Live LLM integration | All LLM tests mock Pydantic AI |
| Subprocess tests | `@pytest.mark.slow`; may skip in CI |

## Running tests

```bash
pipenv install --dev
pipenv run pytest
pipenv run pytest tests/test_research_quality.py -v
pipenv run pytest -m "not slow"
```
