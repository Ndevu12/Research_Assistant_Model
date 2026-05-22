# Research Quality — Known Issues

**Status:** P0–P2 fixes **implemented** (2026-05-22)  
**Recorded:** 2026-05-22  
**Triggering run:** Interactive query `transformer attention mechanisms`  
**Branch context:** `feat/multi-stage-research-pipeline`

---

## Summary

Reports could look **factually wrong or off-topic** even when the pipeline completed successfully. For the reference run, this was **not** primarily an Ollama/LLM accuracy failure: **no LLM calls were made** (`llm_tokens_in: 0`, `synthesis.llm_enabled=false`). The pipeline retrieved a mix of relevant and irrelevant papers, ranked some off-topic work highly, and assembled a misleading executive summary using **heuristic synthesis** and **abstract snippet extraction**.

The fixes below are **query-agnostic** — they use embedding similarity, adaptive corpus-relative thresholds, and generic keyword-collision detection rather than hardcoded NLP/ML domain lists. Multi-domain regression tests live in `tests/test_research_quality.py`.

---

## Reference Run — Observed Symptoms (Pre-Fix)

| Symptom | Example from output |
|---------|---------------------|
| Executive summary off-topic | Opens with *“Air pollution poses a critical global public health challenge…”* for an NLP/transformer query |
| Irrelevant papers in top results | Cervical cancer (CerviFormer), tea evapotranspiration, Arabic sign language, boring machining (PhyDT) |
| Suspicious canonical paper metadata | *Attention Is All You Need* listed as **2025** with DOI `10.65215/2q58a426` |
| Fragmented clustering | Many themes prefixed `Unclustered: …` (8 thin clusters) |
| Generic analysis placeholders | *“Details inferred from abstract only”*, *“Full disagreement analysis requires LLM synthesis”* |
| No relevance pruning | 25 papers kept, **0 filtered** by relevance stage |
| High retrieval volume | 96 papers retrieved → 76 after dedup → 25 ranked |

**Pipeline duration:** ~7.4s (11 stages, no failures)  
**Debug artifact:** `logs/debug/pipeline_*_20260522_*.json` (query: `transformer attention mechanisms`)  
**Ranking top score:** `0.8922` (misleadingly high for topical fit)

---

## Fix Status

| ID | Component | Status | What changed |
|----|-----------|--------|--------------|
| RC-1 | Query expansion | **Fixed** | Phrase-aware synonyms, Jaccard gate, broad-term guard; ML-specific templates removed |
| RC-2 | Ranking | **Fixed** | Embedding weight 30%; embedding outlier + keyword-collision penalties (no ML branch) |
| RC-3 | Relevance gate | **Fixed** | Adaptive embedding floor (percentile + gap-from-top); configurable `min_embedding_similarity` |
| RC-4 | Synthesis & summary | **Fixed** | Top-quartile agreements; template executive summary wired to config thresholds |
| RC-5 | Clustering | **Fixed** | Macro-cluster merge when HDBSCAN noise > 50%; `Theme:` labels instead of singleton spam |
| RC-6 | Metadata / dedup | **Fixed** | Generic year/DOI sanity; `canonical_boost: 0.0` default (registry opt-in) |
| RC-7 | LLM mode | **Fixed** | `llm_mode: auto \| on \| off` via `resolve_llm_features.py` |

---

## Architecture Context

```
Query → expansion (heuristic) → retrieval (OpenAlex + Semantic Scholar)
     → dedup → ranking → relevance_scoring → clustering → synthesis (heuristic)
     → gap_analysis (heuristic) → report_generation
```

| Stage | LLM used? | Quality notes |
|-------|-----------|---------------|
| Query expansion | Auto (off on 3B Ollama) | Heuristic variants with quality gates |
| Retrieval | No | Keyword/API search |
| Ranking | No | Weighted signals + embedding cache |
| Relevance | No | Adaptive embedding floor + concept match |
| Synthesis | Auto | Heuristic path uses embedding-aligned agreements |
| Report | No | Template summary + validated snippet |

---

## Root Cause Analysis (Historical)

These sections document **why** the reference run failed. Each maps to a fix above.

### RC-1: Query expansion produces noisy search strings

**Location:** `src/research/query_expansion.py`

For query `transformer attention mechanisms`, heuristic expansion previously yielded redundant variants like `attention mechanism attention mechanisms`. Fixes: phrase-aware replacement, Jaccard overlap gate, broad-term guard, concept bigrams. **No** transformer/attention-specific templates.

---

### RC-2: Ranking mis-weighted for topical precision

**Location:** `src/research/ranking.py`, `config/default.yaml`

Previously `embedding_similarity` was 5% and `semantic_relevance` was keyword-only. Now embedding weight is 30%, with generic penalties for:

- Partial core-concept coverage
- Embedding outliers (far below top-5 mean similarity)
- Keyword collision (high overlap, low embedding similarity)

Config: `outlier_embedding_gap: 0.12`, `keyword_collision_max_sim: 0.40`.

---

### RC-3: Relevance filter was effectively disabled

**Location:** `src/research/relevance_scoring.py`

Previously filtered only at `rank_score < 0.05`. Now uses composite gate with adaptive embedding floor:

```python
floor = max(min_embedding_similarity, percentile(sims, keep_percentile), top_sim - gap_from_top)
```

Percentile skipped when corpus size < 8. Default `min_embedding_similarity: 0.35`.

---

### RC-4: Heuristic synthesis built misleading narratives

**Location:** `src/analysis/synthesis.py`, `src/reporting/report_generation.py`

Previously `agreements[0]` from rank order drove the executive summary. Now:

- Agreements drawn from top embedding-similarity quartile
- Executive summary uses query + cluster themes template
- Validated snippet only when embedding similarity ≥ configured floor

---

### RC-5: Clustering fragmented into “Unclustered” singletons

**Location:** `src/research/clustering.py`

When HDBSCAN noise ratio > `noise_merge_threshold` (0.5), noise papers merge into ≤4 keyword macro-clusters labeled `Theme: …`.

---

### RC-6: Scholarly metadata quality

**Location:** `src/research/metadata_sanity.py`, `src/retrieval/deduplication.py`

Generic rules: future-year correction, DOI format checks, richer duplicate preference. Canonical work registry is **opt-in** (`canonical_boost: 0.0` default).

---

### RC-7: LLM synthesis disabled by default

**Location:** `src/config/resolve_llm_features.py`, `config/default.yaml`

Tri-state `llm_mode: auto` enables LLM on cloud providers and capable local models (8B+). Small Ollama models (e.g. `llama3.2:3b`) stay heuristic-only unless explicitly overridden.

---

## Quality Modes

| Mode | Typical setup | Synthesis | Expansion |
|------|---------------|-----------|-----------|
| Heuristic-only | `llama3.2:3b`, `llm_mode: auto` | Off | Off |
| Balanced local | `llama3.1:8b`, `llm_mode: auto` | On | On |
| Cloud | `openai` / `anthropic`, `llm_mode: auto` | On | On |

Override with `RA_SYNTHESIS__LLM_MODE=on|off|auto` or legacy `RA_SYNTHESIS__LLM_ENABLED=true|false`.

---

## Reproduction Checklist

Run multi-domain regression (no network):

```bash
pipenv run pytest tests/test_research_quality.py -q
```

Full pipeline smoke test:

```bash
pipenv run python -m src "transformer attention mechanisms"
```

**Expect (post-fix):**

- [ ] Executive summary uses query + cluster themes; no off-topic decoy domain in lead
- [ ] Keyword-collision decoys demoted in ranking and filtered by relevance
- [ ] High HDBSCAN noise yields ≤4 `Theme:` macro-clusters, not N singletons
- [ ] `llm_tokens_in: 0` when running heuristic-only mode on 3B model

**Inspect expansion:**

```bash
pipenv run python -c "
from src.research.query_expansion import expand_query_heuristic, extract_core_concepts
q = 'transformer attention mechanisms'
print(expand_query_heuristic(q, extract_core_concepts(q)))
"
```

---

## Related Configuration

| Setting | Default | Quality impact |
|---------|---------|----------------|
| `synthesis.llm_mode` | `auto` | Model-aware LLM enable (RC-7) |
| `query_expansion.llm_mode` | `auto` | Model-aware expansion (RC-1) |
| `ranking.weights.embedding_similarity` | `0.30` | Primary semantic steering (RC-2) |
| `ranking.outlier_embedding_gap` | `0.12` | Demote embedding outliers (RC-2) |
| `ranking.keyword_collision_max_sim` | `0.40` | Keyword-without-semantics penalty (RC-2) |
| `ranking.canonical_boost` | `0.0` | Opt-in landmark boost (RC-6) |
| `relevance_scoring.min_embedding_similarity` | `0.35` | Base embedding floor (RC-3) |
| `relevance_scoring.adaptive_embedding` | `true` | Corpus-relative floor (RC-3) |
| `clustering.noise_merge_threshold` | `0.5` | Macro-cluster merge trigger (RC-5) |

Environment overrides:

- `RA_RELEVANCE_SCORING__MIN_EMBEDDING_SIMILARITY`
- `RA_SYNTHESIS__LLM_MODE=auto`
- `RA_RANKING__CANONICAL_BOOST=0.05` (opt-in)

---

## Change Log

| Date | Action |
|------|--------|
| 2026-05-22 | Initial documentation from interactive run analysis |
| 2026-05-22 | P0–P2 fixes implemented; multi-domain tests in `test_research_quality.py` |
