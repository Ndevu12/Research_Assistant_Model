# Research Quality — Known Issues

**Status:** Documented — fixes **not yet implemented** (awaiting go-ahead)  
**Recorded:** 2026-05-22  
**Triggering run:** Interactive query `transformer attention mechanisms`  
**Branch context:** `feat/multi-stage-research-pipeline`

---

## Summary

Reports can look **factually wrong or off-topic** even when the pipeline completes successfully. For the reference run, this was **not** primarily an Ollama/LLM accuracy failure: **no LLM calls were made** (`llm_tokens_in: 0`, `synthesis.llm_enabled=false`). The pipeline retrieved a mix of relevant and irrelevant papers, ranked some off-topic work highly, and assembled a misleading executive summary using **heuristic synthesis** and **abstract snippet extraction**.

Treat this document as the backlog for research-quality improvements.

---

## Reference Run — Observed Symptoms

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

## Architecture Context (What Ran)

```
Query → expansion (heuristic) → retrieval (OpenAlex + Semantic Scholar)
     → dedup → ranking → relevance_scoring → clustering → synthesis (heuristic)
     → gap_analysis (heuristic) → report_generation
```

| Stage | LLM used? | Notes |
|-------|-----------|-------|
| Query expansion | No (`query_expansion.llm_enabled=false`) | Heuristic variants only |
| Retrieval | No | Keyword/API search |
| Ranking | No | Weighted signals + embeddings |
| Synthesis | No (`synthesis.llm_enabled=false`) | Abstract snippet heuristics |
| Gap analysis | No | Derived from heuristic synthesis |
| Report | No | Executive summary from synthesis.agreements[0] |

**Config defaults:** `config/default.yaml` — `synthesis.llm_enabled: false`

---

## Root Cause Analysis

### RC-1: Query expansion produces noisy search strings

**Location:** `src/research/query_expansion.py` — `expand_query_heuristic()`, `_expand_synonyms()`

For query `transformer attention mechanisms`, heuristic expansion yields:

```
attention mechanism attention mechanisms
self-attention attention mechanisms
transformer architecture attention mechanisms
transformer attention methods
transformer attention applications
```

**Problems:**

1. **Redundant / ungrammatical variants** (e.g. doubling “attention mechanism”).
2. **Substring synonym replacement** — replacing `transformer` with `attention mechanism` in a query that already contains “attention” dilutes intent.
3. **Over-broad term `attention`** — matches medical, vision, psychology, and generic “attention mechanism” papers unrelated to NLP transformers.
4. **Missing high-value variants** — no explicit `"self-attention"`, `"transformer attention"`, survey/review phrasing, or canonical paper anchors.

**Downstream effect:** `RetrievalStage` searches original + all variants (`src/retrieval/retrieval_stage.py`), multiplying off-topic API hits.

---

### RC-2: Ranking mis-weighted for topical precision

**Location:** `src/research/ranking.py`, weights in `config/default.yaml`

| Signal | Default weight | Issue |
|--------|----------------|-------|
| `semantic_relevance` | 30% | Implemented as **keyword overlap**, not embedding similarity |
| `embedding_similarity` | **5%** | Too low to correct token-collision papers |
| `recency` | 15% | Boosts recent off-topic papers (e.g. 2025 air-pollution transformer paper) |
| `citation_count` | 15% | Popular papers rank high regardless of query fit |
| `keyword_overlap` | 10% | Single-token hits (`attention`, `transformer`) sufficient for a decent score |

**Example failure mode:**  
*A Transformer-Based Deep Learning Approach to Predicting Air Organic Pollutant–Human Protein Interactions* (2025) matches **`Transformer`** in title + recency + citations → ranks #1 despite unrelated domain.

**Evidence:** Debug metrics show `top_score: 0.8922` while executive summary reflects paper #1’s abstract (air pollution).

---

### RC-3: Relevance filter is effectively disabled

**Location:** `src/research/relevance_scoring.py` — `MIN_RELEVANCE_SCORE = 0.05`

- Filters only papers with `rank_score < 0.05`.
- In the reference run: **25 scored, 0 filtered**.
- No embedding-based minimum similarity to query.
- No requirement for **multiple query concepts** to co-occur (e.g. both `transformer` and `attention` in ML sense).

---

### RC-4: Heuristic synthesis builds misleading narratives

**Location:** `src/analysis/synthesis.py`, `src/reporting/report_generation.py`

**Extraction (`_heuristic_extraction`):**

- First 1–2 abstract sentences → `findings`
- Fixed placeholder: `methodology=["Details inferred from abstract only"]`
- Generic fallback: `findings = [f"Discusses {title}."]`

**Collective synthesis (`_heuristic_synthesis`):**

- `agreements = all_findings[:3]` — **first three papers in rank order**, not semantically validated agreements
- `disagreements = ["Full disagreement analysis requires LLM synthesis"]` — hardcoded placeholder
- `gaps` from limitations snippets — often random abstract tails

**Executive summary (`_build_executive_summary`):**

```python
if synthesis and synthesis.agreements:
    parts.append(synthesis.agreements[0])  # ← first ranked paper's abstract lead
```

**Downstream effect:** Report reads like a **wrong answer** because the summary foregrounds whichever paper ranked first, not what the corpus collectively says about the query.

---

### RC-5: Clustering fragments into “Unclustered” singletons

**Location:** `src/research/clustering.py` — HDBSCAN + noise handling

- `min_cluster_size: 2`, `min_samples: 1` in `config/default.yaml`
- HDBSCAN label `-1` (noise) → code creates **one cluster per paper** with theme `Unclustered: {title keywords}`
- Reference run: **8 clusters**, most singletons — poor thematic structure for reporting

**Downstream effect:** Thematic Findings section looks arbitrary; executive summary lists cluster names like `Unclustered: Transformers / Remember / First`.

---

### RC-6: Scholarly metadata quality (duplicate / wrong records)

**Observed:** *Attention Is All You Need* as year **2025**, OpenAlex `W2626778328`, non-standard DOI.

**Location:** Ingestion via `src/retrieval/providers/` — no canonical-title verification or anomaly detection.

**Problems:**

- No boost for known canonical works (Vaswani et al. 2017).
- No penalty for suspicious year/title/DOI combinations.
- Deduplication (`src/retrieval/deduplication.py`) may not merge duplicate records of the same landmark paper.

---

### RC-7: LLM synthesis disabled by default (intentional, but quality cost)

**Location:** `config/default.yaml`, `.env.example`

- Default `synthesis.llm_enabled: false` avoids retry loops on small local models (`llama3.2:3b`).
- Trade-off: fast runs but **no cross-paper reasoning**, no real agreements/disagreements, no query-focused summary.

**Not a bug** — a **documented product default** with known quality impact. Enabling LLM (`RA_SYNTHESIS__LLM_ENABLED=true`) helps but does not fix RC-1–RC-3 alone.

---

## Issue → Component Map

| ID | Component | File(s) |
|----|-----------|---------|
| RC-1 | Query expansion | `src/research/query_expansion.py` |
| RC-2 | Ranking weights / signals | `src/research/ranking.py`, `config/default.yaml`, `config/ranking.yaml` |
| RC-3 | Relevance gate | `src/research/relevance_scoring.py` |
| RC-4 | Heuristic synthesis & summary | `src/analysis/synthesis.py`, `src/reporting/report_generation.py` |
| RC-5 | Clustering noise handling | `src/research/clustering.py`, `config/default.yaml` |
| RC-6 | Metadata / dedup | `src/retrieval/providers/*`, `src/retrieval/deduplication.py` |
| RC-7 | Synthesis mode default | `config/default.yaml`, `.env.example` |

---

## Planned Fix Backlog (Not Implemented)

Priority order for when implementation is approved:

### P0 — High impact, works without LLM

1. **Query expansion hygiene** (RC-1)  
   - Phrase-aware variants; block redundant replacements.  
   - Add ML-specific templates for transformer/attention queries.  
   - Cap variants that share only one broad token with the original.

2. **Stronger relevance gate** (RC-3)  
   - Embedding similarity floor (e.g. drop papers below cosine threshold to query).  
   - Multi-concept requirement for multi-term queries.  
   - Raise or make configurable `MIN_RELEVANCE_SCORE`.

3. **Executive summary safety** (RC-4)  
   - Do not use raw `agreements[0]` from rank order.  
   - Build summary from query + cluster themes + embedding-centroid papers, or require LLM when heuristics would misfire.

4. **Rebalance ranking weights** (RC-2)  
   - Increase `embedding_similarity` (e.g. 25–35%).  
   - Reduce recency/citation influence for literature-review intent.  
   - Optionally use true embedding similarity for `semantic_relevance` signal.

### P1 — Structural quality

5. **Clustering fallback** (RC-5)  
   - When >50% HDBSCAN noise, merge into keyword-based macro-themes instead of N `Unclustered` singletons.

6. **Domain-aware downranking** (RC-2)  
   - Penalize papers where only `attention` matches without `transformer`/`self-attention`/NLP context.

7. **Metadata sanity** (RC-6)  
   - Canonical title registry for landmark papers; flag year/DOI anomalies.

### P2 — LLM-dependent improvements

8. **Enable LLM synthesis when resources allow** (RC-7)  
   - Document in README: `RA_SYNTHESIS__LLM_ENABLED=true` + `llama3.1:8b` or cloud provider.  
   - Keep heuristic fast path as default for constrained machines.

9. **LLM query expansion** (optional)  
   - `query_expansion.llm_enabled=true` for better search variants when local/cloud LLM available.

---

## Reproduction Checklist

To verify issues persist before/after fixes:

```bash
pipenv run python -m src "transformer attention mechanisms"
```

**Expect (pre-fix):**

- [ ] Executive summary may start with unrelated domain (e.g. air pollution)
- [ ] Mix of NLP and non-NLP “transformer/attention” papers in top 25
- [ ] Many `Unclustered:` theme headings
- [ ] `Skipped LLM gap analysis (synthesis.llm_enabled=false)` in warnings
- [ ] Logs: `llm_tokens_in: 0` in debug dump

**Inspect:**

```bash
pipenv run python -c "
from src.research.query_expansion import expand_query_heuristic, extract_core_concepts
q = 'transformer attention mechanisms'
print(expand_query_heuristic(q, extract_core_concepts(q)))
"
ls logs/debug/pipeline_*transformer* 2>/dev/null || ls -t logs/debug/ | head -3
```

---

## Related Configuration

| Setting | Default | Quality impact |
|---------|---------|----------------|
| `synthesis.llm_enabled` | `false` | Heuristic-only synthesis (RC-4, RC-7) |
| `query_expansion.llm_enabled` | `false` | Heuristic expansion only (RC-1) |
| `ranking.weights.embedding_similarity` | `0.05` | Weak semantic steering (RC-2) |
| `ranking.top_k` | `25` | Large tail of marginal papers |
| `clustering.min_cluster_size` | `2` | Many HDBSCAN noise labels (RC-5) |
| `relevance_scoring` threshold | `0.05` | Almost no filtering (RC-3) |

---

## Change Log

| Date | Action |
|------|--------|
| 2026-05-22 | Initial documentation from interactive run analysis |
| — | Fixes pending user go-ahead |
