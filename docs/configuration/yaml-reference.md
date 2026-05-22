# YAML Reference

YAML files in `config/` provide the baseline settings merged into `AppSettings`. Environment variables and `.env` override these values at runtime.

See [Configuration precedence](precedence.md) for load order.

## Files loaded by `AppSettings`

| File | Merged into | Role |
|------|-------------|------|
| `default.yaml` | entire tree | Base defaults for all sections |
| `models.yaml` | `llm` | LLM provider overrides |
| `ranking.yaml` | `ranking` | Ranking weights and top-k |
| `providers.yaml` | `retrieval` | Provider toggles and retrieval limits |

## Files loaded separately

| File | Loader | Role |
|------|--------|------|
| `ollama_models.yaml` | `model_selection.py` | Supported Ollama models, RAM/disk requirements, synthesis hints |
| `canonical_works.yaml` | `canonical_works.py` | Optional DOI/title boosts during ranking |

---

## `default.yaml` — full tree

The base file mirrors all nested models. Key sections:

### LLM

```yaml
llm:
  provider: ollama
  model: auto
  base_url: http://localhost:11434
  temperature: 0.2
  timeout_seconds: 120
```

Env override: `RA_LLM__PROVIDER=openai`, `RA_LLM__MODEL=gpt-4o-mini`.

### Embedding

```yaml
embedding:
  model: BAAI/bge-small-en-v1.5
  batch_size: 32
  cache_dir: data/embeddings
```

Used by deduplication, ranking, relevance scoring, and clustering stages.

### Ranking

```yaml
ranking:
  top_k: 25
  weights:
    semantic_relevance: 0.20
    citation_count: 0.08
    recency: 0.08
    venue_quality: 0.10
    abstract_completeness: 0.10
    keyword_overlap: 0.10
    author_prominence: 0.05
    embedding_similarity: 0.30
  domain_penalty_multiplier: 0.5
  outlier_embedding_gap: 0.12
  keyword_collision_max_sim: 0.40
  canonical_boost: 0.0
```

`ranking.yaml` overlays only this section — edit weights without touching `default.yaml`.

### Query expansion

```yaml
query_expansion:
  llm_mode: auto      # auto | on | off
  max_variants: 5
  max_sub_questions: 3
```

`llm_enabled` defaults to `false` in code; resolved at pipeline start from `llm_mode` and Ollama catalog.

### Deduplication

```yaml
deduplication:
  enabled: true
  enable_embedding_dedup: true
  embedding_similarity_threshold: 0.92
```

### Clustering

```yaml
clustering:
  min_cluster_size: 2
  min_samples: 1
  noise_merge_threshold: 0.5
  max_macro_clusters: 4
```

### Relevance scoring

```yaml
relevance_scoring:
  min_rank_score: 0.25
  min_embedding_similarity: 0.35
  require_all_concepts: true
  min_papers: 5
  concept_match_mode: any_group
  adaptive_embedding: true
  keep_percentile: 25
  gap_from_top: 0.12
```

### Retrieval

```yaml
retrieval:
  concurrency_limit: 4
  per_provider_limit: 8
  providers:
    openalex:
      enabled: true
      limit: 8
    semantic_scholar:
      enabled: true
      limit: 8
    arxiv:
      enabled: false
    crossref:
      enabled: false
    pubmed:
      enabled: false
    core:
      enabled: false
    dblp:
      enabled: false
```

!!! info "Provider `limit` field"
    The retrieval stage uses `per_provider_limit` for all providers. Individual `providers.<name>.limit` values are **not** applied during search.

### Pipeline

```yaml
pipeline:
  continue_on_stage_failure: true
  stage_timeout_seconds: 300
  synthesis_timeout_seconds: 600
  stream_progress: true
  debug: false
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

### Memory

```yaml
memory:
  db_path: data/research.db
  cache_enabled: false
```

Set `cache_enabled: true` to reuse cached retrieval results keyed by query + enabled providers + config hash.

### Synthesis

```yaml
synthesis:
  llm_mode: auto
  max_llm_papers: 3
  extraction_max_retries: 0
  collective_max_retries: 0
  concurrency: 2
  circuit_breaker_failures: 2
```

---

## `models.yaml`

Thin overlay for LLM settings:

```yaml
provider: ollama
model: auto
base_url: http://localhost:11434
temperature: 0.2
timeout_seconds: 120
```

Equivalent env block:

```bash
RA_LLM__PROVIDER=ollama
RA_LLM__MODEL=auto
RA_LLM__BASE_URL=http://localhost:11434
```

---

## `providers.yaml`

Retrieval-only overlay — same structure as the `retrieval:` section in `default.yaml`. Use this file to enable optional providers without editing the base config:

```yaml
providers:
  arxiv:
    enabled: true
  crossref:
    enabled: true
```

Equivalent env:

```bash
RA_RETRIEVAL__PROVIDERS__ARXIV__ENABLED=true
RA_RETRIEVAL__PROVIDERS__CROSSREF__ENABLED=true
```

---

## `ollama_models.yaml`

Not merged into `AppSettings`. Consumed by setup and model auto-selection:

```yaml
auto_select: true
fallback: llama3.2:3b

models:
  - name: llama3.1:8b
    label: Llama 3.1 8B
    min_ram_gb: 8
    recommended_ram_gb: 10
    disk_gb: 5
    priority: 100
    synthesis:
      llm_enabled: true
      max_llm_papers: 5

  - name: llama3.2:3b
    label: Llama 3.2 3B
    min_ram_gb: 4
    recommended_ram_gb: 6
    disk_gb: 2.5
    priority: 50
    synthesis:
      llm_enabled: false
      max_llm_papers: 3
```

When `RA_LLM__MODEL=auto`, setup picks the highest-priority model whose RAM/disk requirements fit the machine. See [Ollama](../llm/ollama.md).

---

## `canonical_works.yaml`

Optional ranking boost for well-known works:

```yaml
works:
  - title: "Attention Is All You Need"
    authors: ["Vaswani"]
    year: 2017
    doi_prefix: "10.48550/arXiv.1706.03762"
```

Controlled by `ranking.canonical_boost` (default `0.0` — no boost until raised).

See also: [Environment variables](environment-variables.md), [Stage toggles](stage-toggles.md), [Retrieval overview](../retrieval/overview.md).
