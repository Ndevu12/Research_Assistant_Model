# Semantic Scholar

Semantic Scholar provides paper metadata and abstracts via the bulk search API. Enabled by default alongside OpenAlex.

Implementation: `src/retrieval/providers/semantic_scholar.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://api.semanticscholar.org/graph/v1/paper/search/bulk` |
| Query params | `query`, `limit`, `fields=title,abstract,year,venue,url,externalIds` |
| Authentication | Optional — `S2_API_KEY` env → `x-api-key` header |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |
| Rate limiting | HTTP 429 → sleep `Retry-After` (default 60s) |

### Example request

```http
GET https://api.semanticscholar.org/graph/v1/paper/search/bulk?query=transformer+attention&limit=8&fields=title,abstract,year,venue,url,externalIds
x-api-key: YOUR_KEY   # optional
```

### API key

| Variable | Required | Effect |
|----------|----------|--------|
| `S2_API_KEY` | No | Higher rate limits when set |

Without a key, anonymous rate limits apply. For heavy interactive use or batch jobs, set `S2_API_KEY` in `.env`.

## Normalization

| S2 field | `RetrievedPaper` field |
|----------|------------------------|
| `title` | `title` |
| `abstract` | `abstract` |
| `year` | `year` |
| `venue` | `venue` |
| `url` | `url` |
| `externalIds.DOI` | `doi` (prefixed with `https://doi.org/` if needed) |

Citation count is not always present in the requested field set; ranking may rely more on embedding similarity for S2-sourced papers.

## Configuration

```yaml
retrieval:
  providers:
    semantic_scholar:
      enabled: true
```

```bash
S2_API_KEY=your_api_key_here
RA_RETRIEVAL__PROVIDERS__SEMANTIC_SCHOLAR__ENABLED=true
```

## Health check

Minimal search with `limit=1` against the bulk endpoint, 15s timeout.

## Operational notes

- Watch for 429 responses in logs — the client waits and retries automatically
- Bulk search is used (not single-paper lookup) for query-variant parallelism
- Combined with OpenAlex, provides good recall for CS/ML topics

See also: [Provider matrix](../provider-matrix.md), [Environment variables](../../configuration/environment-variables.md#retrieval-ra_retrieval__).
