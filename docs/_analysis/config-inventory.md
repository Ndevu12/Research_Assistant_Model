# AppSettings / Config Inventory

Source: `src/config/settings.py`, `config/*.yaml`, `.env.example`, `src/config/resolve_llm_features.py`, `src/config/model_selection.py`.

## Load precedence

| Priority | Source | Mechanism |
|----------|--------|-----------|
| 1 (highest) | Constructor kwargs | `AppSettings(retrieval={...})` |
| 2 | Process environment | `RA_` prefix, nested `__` delimiter |
| 3 | `.env` file | Same rules as env (`env_file` in `SettingsConfigDict`) |
| 4 | Merged YAML | `YamlSettingsSource` → `load_yaml_config()` |
| 5 (lowest) | Pydantic field defaults | Nested model defaults in `settings.py` |

**Post-load resolution:** `resolve_effective_settings()` at pipeline start computes effective `synthesis.llm_enabled`, `query_expansion.llm_enabled`, and Ollama `max_llm_papers` hints.

**Alternate loader:** `AppSettings.from_yaml()` — constructor > env > YAML > defaults; **skips `.env`**.

### Doc/code discrepancies

| Topic | Code | README / `.env.example` | Action for Phase 1 |
|-------|------|-------------------------|-------------------|
| Precedence order | init > env > .env > yaml > defaults | README: env > .env > yaml | Document constructor kwargs as highest |
| `AppSettings` docstring | Omits `.env` step | — | Fix docstring or docs to match runtime |
| `RA_LLM__BASE_URL` default | `http://localhost:11434` (no `/v1`) | `.env.example` uses `/v1` | Document Ollama normalizes via `normalize_openai_base_url()` |
| Debug | `RA_PIPELINE__DEBUG` + `RA_DEBUG` | `.env.example` has `RA_DEBUG=1` active | Warn that example enables debug |
| CrossRef mailto | Optional (fallback User-Agent) | "Required when enabled" | Clarify polite-pool recommendation vs requirement |
| Per-provider limit | `ProviderConfig.limit` exists | Not documented | Document that pipeline uses `per_provider_limit` only |

---

## Top-level `AppSettings` fields

| Field | Type | Env prefix | Default factory |
|-------|------|------------|-----------------|
| `llm` | `LLMConfig` | `RA_LLM__*` | `LLMConfig()` |
| `embedding` | `EmbeddingConfig` | `RA_EMBEDDING__*` | `EmbeddingConfig()` |
| `ranking` | `RankingConfig` | `RA_RANKING__*` | `RankingConfig()` |
| `query_expansion` | `QueryExpansionConfig` | `RA_QUERY_EXPANSION__*` | `QueryExpansionConfig()` |
| `deduplication` | `DeduplicationConfig` | `RA_DEDUPLICATION__*` | `DeduplicationConfig()` |
| `clustering` | `ClusteringConfig` | `RA_CLUSTERING__*` | `ClusteringConfig()` |
| `relevance_scoring` | `RelevanceScoringConfig` | `RA_RELEVANCE_SCORING__*` | `RelevanceScoringConfig()` |
| `retrieval` | `RetrievalConfig` | `RA_RETRIEVAL__*` | `RetrievalConfig()` |
| `pipeline` | `PipelineConfig` | `RA_PIPELINE__*` | `PipelineConfig()` |
| `memory` | `MemoryConfig` | `RA_MEMORY__*` | `MemoryConfig()` |
| `synthesis` | `SynthesisConfig` | `RA_SYNTHESIS__*` | `SynthesisConfig()` |

### Non-`AppSettings` env vars

| Variable | Read in | Purpose |
|----------|---------|---------|
| `RA_CONFIG_DIR` | `settings.py` | Override config directory |
| `RA_DEBUG` | `settings.debug_enabled` | Debug alias (`1`/`true`/`yes`) |
| `S2_API_KEY` | `semantic_scholar.py` | Semantic Scholar API key |
| `RA_CROSSREF_MAILTO` / `CROSSREF_MAILTO` | `crossref.py` | CrossRef polite-pool User-Agent |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_API_KEY` | `src/models/*` | LLM keys (fallback if `RA_LLM__API_KEY` unset) |

---

## Nested models — fields and defaults

### `LLMConfig`

| Field | Default | Env example |
|-------|---------|-------------|
| `provider` | `"ollama"` | `RA_LLM__PROVIDER` |
| `model` | `"auto"` | `RA_LLM__MODEL` |
| `base_url` | `"http://localhost:11434"` | `RA_LLM__BASE_URL` |
| `api_key` | `None` | `RA_LLM__API_KEY` |
| `temperature` | `0.2` | `RA_LLM__TEMPERATURE` |
| `timeout_seconds` | `120` | `RA_LLM__TIMEOUT_SECONDS` |

**Unused at runtime:** `temperature`, `timeout_seconds` (not passed to pydantic-ai models; stage timeouts are pipeline-level).

### `EmbeddingConfig`

| Field | Default |
|-------|---------|
| `model` | `"BAAI/bge-small-en-v1.5"` |
| `batch_size` | `32` |
| `cache_dir` | `"data/embeddings"` |

### `RankingWeights`

| Field | Default |
|-------|---------|
| `semantic_relevance` | `0.20` |
| `citation_count` | `0.08` |
| `recency` | `0.08` |
| `venue_quality` | `0.10` |
| `abstract_completeness` | `0.10` |
| `keyword_overlap` | `0.10` |
| `author_prominence` | `0.05` |
| `embedding_similarity` | `0.30` |

### `RankingConfig`

| Field | Default |
|-------|---------|
| `top_k` | `25` |
| `weights` | `RankingWeights()` |
| `domain_penalty_multiplier` | `0.5` |
| `outlier_embedding_gap` | `0.12` |
| `keyword_collision_max_sim` | `0.40` |
| `canonical_boost` | `0.0` |

### `QueryExpansionConfig`

| Field | Default | Notes |
|-------|---------|-------|
| `llm_mode` | `"auto"` | `on` \| `off` \| `auto` |
| `llm_enabled` | `False` | Resolved at pipeline start |
| `max_variants` | `5` | |
| `max_sub_questions` | `3` | |

### `DeduplicationConfig`

| Field | Default |
|-------|---------|
| `enabled` | `True` |
| `enable_embedding_dedup` | `True` |
| `embedding_similarity_threshold` | `0.92` |

### `ClusteringConfig`

| Field | Default |
|-------|---------|
| `min_cluster_size` | `2` |
| `min_samples` | `1` |
| `noise_merge_threshold` | `0.5` |
| `max_macro_clusters` | `4` |

### `RelevanceScoringConfig`

| Field | Default |
|-------|---------|
| `min_rank_score` | `0.25` |
| `min_embedding_similarity` | `0.35` |
| `require_all_concepts` | `True` |
| `min_papers` | `5` |
| `concept_match_mode` | `"any_group"` |
| `adaptive_embedding` | `True` |
| `keep_percentile` | `25.0` |
| `gap_from_top` | `0.12` |

### `ProviderConfig`

| Field | Default |
|-------|---------|
| `enabled` | `True` |
| `limit` | `8` |

### `RetrievalConfig`

| Field | Default |
|-------|---------|
| `concurrency_limit` | `4` |
| `per_provider_limit` | `8` |
| `providers` | see table below |

**Default provider toggles (code):**

| Provider key | `enabled` | `limit` |
|--------------|-----------|---------|
| `openalex` | `True` | `8` |
| `semantic_scholar` | `True` | `8` |
| `arxiv` | `False` | `8` |
| `crossref` | `False` | `8` |
| `pubmed` | `False` | `8` |
| `core` | `False` | `8` |
| `dblp` | `False` | `8` |

**Env examples:**  
`RA_RETRIEVAL__CONCURRENCY_LIMIT`, `RA_RETRIEVAL__PER_PROVIDER_LIMIT`,  
`RA_RETRIEVAL__PROVIDERS__ARXIV__ENABLED=true`

### `PipelineConfig`

| Field | Default |
|-------|---------|
| `continue_on_stage_failure` | `True` |
| `stage_timeout_seconds` | `300` |
| `synthesis_timeout_seconds` | `600` |
| `stream_progress` | `True` |
| `debug` | `False` |
| `enabled_stages.*` | all 11 stages `True` |

### `MemoryConfig`

| Field | Default |
|-------|---------|
| `db_path` | `"data/research.db"` |
| `cache_enabled` | `False` |

### `SynthesisConfig`

| Field | Default | Notes |
|-------|---------|-------|
| `llm_mode` | `"auto"` | |
| `llm_enabled` | `False` | Resolved at pipeline start |
| `max_llm_papers` | `3` | May be overridden by Ollama catalog hints |
| `concurrency` | `2` | |
| `circuit_breaker_failures` | `2` | |

### `debug_enabled` (computed property)

```python
env_debug = os.environ.get("RA_DEBUG", "").lower() in {"1", "true", "yes"}
return self.pipeline.debug or env_debug
```

---

## YAML files in `config/`

| File | Loaded by `AppSettings`? | Merge target | Purpose |
|------|---------------------------|--------------|---------|
| `default.yaml` | Yes (base) | entire settings tree | Full default mirror |
| `models.yaml` | Yes | `llm` section | LLM overrides |
| `ranking.yaml` | Yes | `ranking` section | Ranking overrides |
| `providers.yaml` | Yes | `retrieval` section | Provider toggles |
| `ollama_models.yaml` | **No** | — | Ollama catalog; loaded by `model_selection.py` |
| `canonical_works.yaml` | **No** | — | Ranking boost; loaded by `canonical_works.py` |

### `ollama_models.yaml` structure

- `auto_select: bool`
- `fallback: model_name`
- `models[]`: `name`, `label`, `min_ram_gb`, `recommended_ram_gb`, `disk_gb`, `priority`, `synthesis.llm_enabled`, `synthesis.max_llm_papers`

### `canonical_works.yaml` structure

- `works[]`: `title`, `authors[]`, `year`, `doi_prefix`

---

## `.env.example` inventory

| Variable | In example | Notes |
|----------|------------|-------|
| `S2_API_KEY` | commented | Semantic Scholar |
| `RA_CROSSREF_MAILTO` / `CROSSREF_MAILTO` | commented | CrossRef |
| `RA_LLM__PROVIDER` | `ollama` | |
| `RA_LLM__MODEL` | `auto` | |
| `RA_LLM__BASE_URL` | `http://localhost:11434/v1` | |
| `RA_LLM__API_KEY` | `ollama` | |
| `RA_SYNTHESIS__LLM_ENABLED` | commented | |
| OpenAI / Anthropic blocks | commented | |
| `RA_RANKING__TOP_K` | `25` | |
| `RA_PIPELINE__DEBUG` | `false` | |
| `RA_PIPELINE__STREAM_PROGRESS` | `true` | |
| `RA_DEBUG` | **`1` (active)** | Enables debug despite `pipeline.debug=false` |
| `RA_CONFIG_DIR` | commented | |

---

## LLM feature resolution env vars

| Env var | Effect |
|---------|--------|
| `RA_SYNTHESIS__LLM_ENABLED` | Force synthesis LLM on/off (overrides `llm_mode`) |
| `RA_QUERY_EXPANSION__LLM_ENABLED` | Force query expansion LLM on/off |
| `RA_SYNTHESIS__LLM_MODE` | `auto` \| `on` \| `off` |
| `RA_QUERY_EXPANSION__LLM_MODE` | `auto` \| `on` \| `off` |

See [llm-resolution-tree.md](llm-resolution-tree.md) for full decision tree.
