# Improvement Roadmap: Accuracy & Research Depth

This document defines the project's improvement direction for the next development cycles. Its focus is raising the factual accuracy of generated reports, grounding them in more real data, and closing the quality gap between the current pipeline and state-of-the-art research assistants.

Related reading: [Heuristic vs LLM modes](../llm/heuristic-vs-llm.md), [Known issues](../quality/known-issues.md), [Provider matrix](../retrieval/provider-matrix.md), [Pipeline stages](../architecture/pipeline-stages.md).

## Current-state assessment

The pipeline is architecturally sound — composable stages, provider registries, layered configuration, graceful degradation — but three structural limits cap report quality:

1. **Heuristic-first analysis.** With `synthesis.llm_enabled` defaulting to `false`, synthesis reduces to sentence extraction from abstracts. The off-topic-report incident documented in [Known issues](../quality/known-issues.md) occurred on a run with zero LLM calls.
2. **Abstract-only evidence.** The `src/fulltext/` package (PDF download, chunking, retrieval-augmented analysis) is interface stubs. Every downstream stage reasons over roughly 150 words per paper; methods, results, and limitations sections are never seen.
3. **One-shot, unverified flow.** Retrieval runs once per query with no coverage assessment, no follow-up queries, and no verification of synthesized claims against sources.

## Goals

- Every claim in a report is traceable to a specific paper and, where full text is available, a supporting passage.
- Retrieval recall and ranking precision are measured, not assumed.
- The LLM is the default analysis engine, with heuristics as the offline fallback rather than the primary path.

## Phase 1 — Retrieval depth and data integrity

**Objective:** more real papers in, bad metadata out.

- Implement the stubbed retrieval providers — PubMed (E-utilities), DBLP, and CORE. Their `normalize()` logic already exists; only the HTTP search half is missing.
- Add **citation-graph snowballing**: after ranking, fetch references and citations of the top-ranked papers (Semantic Scholar / OpenAlex citation endpoints) and feed them back through deduplication and ranking. This is the highest-impact recall lever available.
- Add **cross-provider metadata verification**: reconcile year, DOI, and venue across providers before a paper enters a report, eliminating the fabricated-metadata failure class recorded in Known issues.

**Exit criteria:** at least two new providers enabled in the provider matrix; snowballing measurably increases relevant-paper recall on the evaluation set (Phase 5); zero unreconciled DOI/year mismatches in generated reports.

## Phase 2 — Full-text grounding (RAG)

**Objective:** reports cite passages, not just titles.

- Implement `src/fulltext/`: resolve open-access PDFs via OpenAlex OA locations, Unpaywall, and arXiv; parse with GROBID (structure-aware) with PyMuPDF as the lightweight fallback; chunk section-aware; embed chunks into the existing embedding cache.
- Extend synthesis to retrieve grounded passages per question and attach paper ID plus supporting quote to every claim.

**Exit criteria:** for open-access papers, synthesis claims carry passage-level citations; the report renderer displays them.

## Phase 3 — Model layer upgrade

**Objective:** state-of-the-art retrieval quality and schema-safe LLM output.

- **Two-stage retrieval:** upgrade the embedding model from `bge-small-en-v1.5` to a current multilingual model (e.g. `bge-m3` or `nomic-embed-text-v1.5`) and add a cross-encoder reranker (e.g. `bge-reranker-v2-m3`) over the top candidates. Add BM25 lexical scoring fused with dense scores (reciprocal rank fusion).
- **Native structured outputs:** replace the JSON-repair layer in `src/utils/` with schema-enforced outputs through pydantic-ai (`output_type`) on providers that support it, shrinking the response-handling surface substantially.
- **Default to a capable model:** flip `llm_mode` to `on` by default. Recommended tiering — per-paper extraction on a mid-tier cloud model (e.g. `claude-sonnet-5`) or a strong local model where offline operation is required; final cross-paper synthesis on a top-tier model (e.g. `claude-opus-5`); batch APIs and prompt caching to control cost. Update the cloud-provider documentation, which currently references retired model names.
- Replace the hardcoded, ML-specific synonym dictionaries in query expansion with LLM-driven expansion so non-ML domains (medicine, economics) expand correctly.

**Exit criteria:** reranked retrieval beats the current ranking on nDCG in the evaluation harness; structured-output path removes the retry/repair machinery for supported providers.

## Phase 4 — Iterative research loop with verification

**Objective:** behave like a deep-research agent, not a single pass.

- Add a coverage-assessment loop stage: after ranking, the LLM evaluates whether the evidence answers the query, generates targeted follow-up queries, and re-enters retrieval until saturation or a configured budget.
- Add a claim-verification pass: a checker validates each synthesized claim against its cited source and drops or flags unsupported claims before report generation.

**Exit criteria:** multi-concept queries trigger at least one refinement round when coverage is thin; unsupported claims are flagged in the report rather than presented as fact.

## Phase 5 — Evaluation harness (prerequisite for all tuning)

**Objective:** every change above proves itself against numbers.

- Build a golden evaluation set of ~20 queries across domains with known-relevant papers.
- Track retrieval recall@k and nDCG, citation validity (DOI resolves, title matches), and synthesis faithfulness (LLM-as-judge scoring against source passages).
- Run the harness in CI alongside the existing research-quality regression tests so accuracy regressions block merges.

**Exit criteria:** dashboards/metrics exist for all three dimensions; Phases 1–4 land with before/after numbers.

## Sequencing and priorities

| Priority | Work item | Impact | Effort |
|----------|-----------|--------|--------|
| P0 | Evaluation harness (Phase 5) | Enables everything else | Medium |
| P0 | Citation snowballing + metadata verification (Phase 1) | High | Medium |
| P1 | Cross-encoder reranker + embedding upgrade (Phase 3) | High | Low–Medium |
| P1 | Stub providers: PubMed, DBLP, CORE (Phase 1) | Medium | Low |
| P2 | Full-text RAG (Phase 2) | Highest single quality jump | High |
| P2 | Structured outputs + LLM-default modes (Phase 3) | High | Medium |
| P3 | Iterative loop + claim verification (Phase 4) | High | High |

Phase 5 and the Phase 1 items ship first: they need no new infrastructure and make every subsequent phase measurable. Phase 2 is the largest single quality improvement and proceeds in parallel once evaluation is in place.

## Out of scope for this cycle

- Non-scholarly sources (news, blogs, patents).
- Multi-user or hosted deployment concerns; the project remains local-first.
- UI work beyond the terminal experience already in flight.
