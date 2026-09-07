# Environment Variables

Authoritative reference for configuration loaded by `AppSettings` (`src/config/settings.py`) and provider-specific env vars read at HTTP call time.

Copy [`.env.example`](https://github.com/Ndevu12/Research_Assistant_Model/blob/main/.env.example) to `.env` for local overrides. See [Configuration precedence](precedence.md) for merge order.

## Naming convention

- Prefix: `RA_`
- Nested settings: double underscore `__` mirrors YAML nesting
- Example: `ranking.top_k` → `RA_RANKING__TOP_K`

Boolean env values accept standard truthy strings (`true`, `1`, `yes`).

---

## App-wide

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_CONFIG_DIR` | `config/` (project root) | Override directory for YAML files |
| `RA_DEBUG` | unset | Alias for debug mode (`1`, `true`, `yes`) — OR-combined with `RA_PIPELINE__DEBUG` |
| `RA_SKIP_SETUP_CHECK` | unset | Skip the Ollama setup/health check on startup (CI, containers) |
| `RA_CONSOLE_LOG_LEVEL` | `WARNING` | Log level shown on the console; files always get full detail |

---

## LLM (`RA_LLM__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_LLM__PROVIDER` | `ollama` | `ollama`, `openai`, or `anthropic` |
| `RA_LLM__MODEL` | `auto` | Model name; `auto` selects from `config/ollama_models.yaml` (Ollama only) |
| `RA_LLM__BASE_URL` | `http://localhost:11434` | API base URL (Ollama OpenAI-compatible endpoint) |

!!! info "Ollama base URL (`/v1` suffix)"
    `config/default.yaml` uses `http://localhost:11434` (no `/v1`); `.env.example` uses `/v1`. Both are valid — `normalize_openai_base_url()` in `src/models/base.py` appends `/v1` when missing. See also [Configuration precedence](precedence.md#common-pitfalls).
| `RA_LLM__API_KEY` | `None` | Unified API key; checked before provider-specific keys |
| `RA_LLM__TEMPERATURE` | `0.2` | Defined in config; **not currently passed to pydantic-ai models** |
| `RA_LLM__TIMEOUT_SECONDS` | `120` | Defined in config; stage timeouts use pipeline settings instead |

**Provider-specific key fallbacks** (when `RA_LLM__API_KEY` is unset):

| Variable | Provider |
|----------|----------|
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `OLLAMA_API_KEY` | Ollama (placeholder; server ignores it) |

---

## Synthesis & query expansion

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_SYNTHESIS__LLM_ENABLED` | `false` | Force LLM synthesis on/off (overrides `llm_mode`) |
| `RA_SYNTHESIS__LLM_MODE` | `auto` | `auto` \| `on` \| `off` — resolved at pipeline start |
| `RA_SYNTHESIS__MAX_LLM_PAPERS` | `3` | Max papers sent to LLM synthesis |
| `RA_SYNTHESIS__CONCURRENCY` | `2` | Parallel LLM synthesis workers |
| `RA_QUERY_EXPANSION__LLM_ENABLED` | `false` | Force LLM query expansion on/off |
| `RA_QUERY_EXPANSION__LLM_MODE` | `auto` | `auto` \| `on` \| `off` |
| `RA_QUERY_EXPANSION__MAX_VARIANTS` | `5` | Max expanded search variants |
| `RA_QUERY_EXPANSION__MAX_SUB_QUESTIONS` | `3` | Max sub-questions from query understanding |

!!! tip "Quality vs speed"
    Defaults keep synthesis and query expansion **heuristic** (`llm_enabled: false`). Enable LLM features for 8B+ local models or cloud providers. See [Heuristic vs LLM](../llm/heuristic-vs-llm.md).

---

## Ranking (`RA_RANKING__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_RANKING__TOP_K` | `25` | Papers kept after ranking |
| `RA_RANKING__WEIGHTS__SEMANTIC_RELEVANCE` | `0.20` | Ranking weight |
| `RA_RANKING__WEIGHTS__EMBEDDING_SIMILARITY` | `0.30` | Ranking weight |
| `RA_RANKING__DOMAIN_PENALTY_MULTIPLIER` | `0.5` | Penalty for off-domain papers |
| `RA_RANKING__CANONICAL_BOOST` | `0.0` | Boost for works in `canonical_works.yaml` |

Full weight list: [YAML reference](yaml-reference.md#ranking).

---

## Retrieval (`RA_RETRIEVAL__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_RETRIEVAL__CONCURRENCY_LIMIT` | `4` | Max parallel searches across query variants |
| `RA_RETRIEVAL__PER_PROVIDER_LIMIT` | `8` | Results per provider per query variant (**actual search limit**) |
| `RA_RETRIEVAL__PROVIDERS__<NAME>__ENABLED` | see below | Enable/disable a provider |
| `RA_RETRIEVAL__PROVIDERS__<NAME>__LIMIT` | `8` | **Ignored** at runtime — use `PER_PROVIDER_LIMIT` |

**Default provider toggles:**

| Provider | Default enabled |
|----------|-----------------|
| `openalex` | `true` |
| `semantic_scholar` | `true` |
| `arxiv`, `crossref`, `pubmed`, `core`, `dblp` | `false` |

**Retrieval API keys (not `RA_`-prefixed):**

| Variable | Required | Description |
|----------|----------|-------------|
| `S2_API_KEY` | No | Semantic Scholar — higher rate limits when set |
| `RA_CROSSREF_MAILTO` | Recommended | CrossRef polite pool (User-Agent mailto) |
| `CROSSREF_MAILTO` | Recommended | Alias for CrossRef mailto |
| `NCBI_API_KEY` | No | PubMed E-utilities — higher rate limits when set |
| `CORE_API_KEY` | For `core` | Required when the CORE provider is enabled |

---

## Pipeline (`RA_PIPELINE__*`)

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_PIPELINE__DEBUG` | `false` | Write JSON debug dumps to `logs/debug/` after each run |
| `RA_PIPELINE__STREAM_PROGRESS` | `true` | Live Rich progress on stderr (TTY only) |
| `RA_PIPELINE__CONTINUE_ON_STAGE_FAILURE` | `true` | Heuristic recovery instead of abort |
| `RA_PIPELINE__STAGE_TIMEOUT_SECONDS` | `300` | Per-stage timeout (except synthesis) |
| `RA_PIPELINE__SYNTHESIS_TIMEOUT_SECONDS` | `600` | Synthesis stage timeout |
| `RA_PIPELINE__ENABLED_STAGES__<STAGE>` | `true` | Disable individual pipeline stages |

Stage names: `query_understanding`, `query_expansion`, `retrieval`, `deduplication`, `ranking`, `snowball`, `rerank`, `relevance_scoring`, `research_loop`, `fulltext`, `clustering`, `synthesis`, `gap_analysis`, `verification`, `citation_export`, `report_generation`. See [Stage toggles](stage-toggles.md).

---

## Snowball, rerank, fulltext

| Variable | Default | Description |
|----------|---------|-------------|
| `RA_SNOWBALL__ENABLED` | `true` | Citation-graph expansion of top-ranked papers |
| `RA_SNOWBALL__MAX_SEED_PAPERS` | `5` | Seeds for the one-hop expansion |
| `RA_SNOWBALL__MAX_NEW_PAPERS` | `30` | Cap on candidates entering re-ranking |
| `RA_RERANK__ENABLED` | `true` | Cross-encoder reranking of the top papers |
| `RA_RERANK__MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Any sentence-transformers cross-encoder |
| `RA_RERANK__TOP_N` | `25` | Papers scored by the cross-encoder |
| `RA_RERANK__BLEND_WEIGHT` | `0.5` | Cross-encoder share of the final score |
| `RA_FULLTEXT__ENABLED` | `true` | Open-access full-text grounding |
| `RA_FULLTEXT__MAX_PAPERS` | `5` | Top papers attempted per run |
| `RA_FULLTEXT__MAX_PDF_MB` | `15` | Per-PDF download size cap |
| `RA_FULLTEXT__TOP_CHUNKS_PER_PAPER` | `3` | Passages retrieved per paper |
| `RA_RESEARCH_LOOP__ENABLED` | `true` | Coverage-driven retrieval refinement |
| `RA_RESEARCH_LOOP__MAX_ITERATIONS` | `1` | Refinement rounds per run |
| `RA_VERIFICATION__ENABLED` | `true` | Claim verification before reporting |
| `RA_VERIFICATION__MIN_TERM_COVERAGE` | `0.5` | Heuristic support threshold |

Full key lists live on the stage pages: [Snowball](../architecture/stages/snowball.md), [Rerank](../architecture/stages/rerank.md), [Fulltext](../architecture/stages/fulltext.md), [Research loop](../architecture/stages/research-loop.md), [Verification](../architecture/stages/verification.md).

---

## Embedding, deduplication, clustering, relevance, memory

| Variable | Default | Section |
|----------|---------|---------|
| `RA_EMBEDDING__MODEL` | `BAAI/bge-small-en-v1.5` | Embedding model |
| `RA_EMBEDDING__BATCH_SIZE` | `32` | Embedding batch size |
| `RA_EMBEDDING__CACHE_DIR` | `data/embeddings` | Disk cache for embeddings |
| `RA_DEDUPLICATION__ENABLED` | `true` | Enable dedup stage logic |
| `RA_DEDUPLICATION__EMBEDDING_SIMILARITY_THRESHOLD` | `0.92` | Embedding dedup threshold |
| `RA_CLUSTERING__MIN_CLUSTER_SIZE` | `2` | HDBSCAN min cluster size |
| `RA_CLUSTERING__MAX_MACRO_CLUSTERS` | `4` | Max thematic clusters in report |
| `RA_RELEVANCE_SCORING__MIN_RANK_SCORE` | `0.25` | Minimum rank score to keep |
| `RA_RELEVANCE_SCORING__MIN_PAPERS` | `5` | Minimum papers after filtering |
| `RA_MEMORY__DB_PATH` | `data/research.db` | SQLite session database |
| `RA_MEMORY__CACHE_ENABLED` | `false` | Cache retrieval results across runs |

---

## Quick copy-paste blocks

**Cloud OpenAI with LLM synthesis:**

```bash
RA_LLM__PROVIDER=openai
RA_LLM__MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
RA_SYNTHESIS__LLM_ENABLED=true
RA_QUERY_EXPANSION__LLM_ENABLED=true
```

**Enable arXiv + CrossRef (full pipeline / API only):**

```bash
RA_RETRIEVAL__PROVIDERS__ARXIV__ENABLED=true
RA_RETRIEVAL__PROVIDERS__CROSSREF__ENABLED=true
RA_CROSSREF_MAILTO=you@example.com
```

**Debug mode:**

```bash
RA_PIPELINE__DEBUG=true
# or
RA_DEBUG=1
```

See also: [Configuration precedence](precedence.md), [YAML reference](yaml-reference.md), [Configuration cookbook](../user-guide/configuration-cookbook.md).
