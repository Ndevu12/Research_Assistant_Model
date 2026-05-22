# arXiv

arXiv covers preprints and e-prints, especially strong for CS, ML, and physics. Disabled by default — enable for the **full pipeline** or API (not the CLI batch shortcut).

Implementation: `src/retrieval/providers/arxiv.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://export.arxiv.org/api/query` |
| Query params | `search_query`, `start=0`, `max_results` |
| Response format | Atom XML |
| Authentication | None |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |

### Query syntax

The provider preserves arXiv field syntax when present:

| User query | `search_query` sent |
|------------|---------------------|
| `ti:attention abs:transformer` | unchanged |
| `transformer attention` | `all:transformer attention` |

Field prefixes: `ti:` (title), `abs:` (abstract), `au:` (author), etc.

### Example request

```http
GET https://export.arxiv.org/api/query?search_query=all:transformer+attention&start=0&max_results=8
```

## Normalization

Atom entries parse to `RetrievedPaper`:

| Atom element | `RetrievedPaper` field |
|--------------|------------------------|
| `title` | `title` |
| `summary` | `abstract` |
| `published` year | `year` |
| `arxiv:primary_category` | `venue` (category label) |
| PDF link or `id` | `url` |
| `arxiv:doi` if present | `doi` |
| Author list | `authors` |

## Configuration

```yaml
retrieval:
  providers:
    arxiv:
      enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__ARXIV__ENABLED=true
```

!!! info "CLI limitation"
    `python -m src "query"` does not enable arXiv. Use interactive mode, the API, or `run_research()` with custom settings.

## Health check

Search with `max_results=1`, 15s timeout.

## Operational notes

- arXiv requests a 3-second delay between calls in their terms of use — the pipeline's concurrency limit helps avoid hammering the API
- Preprint-heavy results may rank differently than peer-reviewed venues from OpenAlex/CrossRef
- Good complement when researching very recent ML work not yet indexed elsewhere

See also: [Provider matrix](../provider-matrix.md), [Configuration cookbook](../../user-guide/configuration-cookbook.md).
