# Fulltext (Grounded Passages)

The fulltext stage runs between [relevance scoring](relevance-scoring.md)
and [clustering](clustering.md). For the top relevance-filtered papers it
resolves open-access PDFs, downloads and parses them, chunks the text
section-aware, and retrieves the passages most relevant to the query. The
passages ground synthesis: extractions quote verbatim evidence, and
reports show it under each paper as **Evidence (from full text)** — the
difference between a summary generator and a research assistant whose
claims can be checked.

## Flow

1. **Resolve** — metadata-first, no extra API calls: arXiv IDs map
   directly to PDF URLs, OpenAlex work records already carry open-access
   locations in raw metadata, and CORE results expose download URLs.
   Closed-access papers simply resolve to nothing.
2. **Download** — cached under `data/fulltext/` keyed by paper ID, with
   size and content-type guards (`CachingPDFDownloader`).
3. **Parse** — PyMuPDF text extraction with heuristic section detection;
   the references section is truncated to keep bibliography noise out of
   retrieval (`src/fulltext/parser.py`).
4. **Chunk** — paragraphs packed into overlapping windows that carry
   their section name (`SectionAwareChunker`).
5. **Retrieve** — chunks are embedded through the existing embedding
   provider and searched by cosine similarity, falling back to BM25 when
   the embedding backend is unavailable (`InMemoryFulltextIndex`).

The per-paper passages land in the `fulltext_passages` artifact.
Synthesis includes them in extraction prompts (LLM mode asks for short
verbatim quotes; heuristic mode attaches trimmed passages directly), and
the markdown renderer prints the quotes under each paper.

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `fulltext.enabled` | `true` | Toggle the stage |
| `fulltext.max_papers` | `5` | Top papers attempted per run |
| `fulltext.max_pdf_mb` | `15` | Per-PDF download size cap |
| `fulltext.request_timeout_seconds` | `30` | Per-download timeout |
| `fulltext.cache_dir` | `data/fulltext` | PDF cache location |
| `fulltext.chunk_chars` / `chunk_overlap` | `1400` / `200` | Chunk window sizing |
| `fulltext.top_chunks_per_paper` | `3` | Passages retrieved per paper |

## Failure behavior

Grounding is best-effort by design: closed-access papers, failed
downloads, malformed PDFs, or a missing `pymupdf` backend reduce coverage
and never break the run. Stage metrics report PDFs resolved, downloaded,
chunks indexed, and papers that ended up with passages.
