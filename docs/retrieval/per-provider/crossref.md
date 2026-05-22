# CrossRef

CrossRef indexes DOI-registered scholarly works across publishers. Disabled by default — enable for full pipeline or API runs.

Implementation: `src/retrieval/providers/crossref.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://api.crossref.org/works` |
| Query params | `query`, `rows` |
| Authentication | Polite pool via `User-Agent` mailto (recommended) |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |
| Rate limiting | HTTP 429 → sleep `Retry-After` |

### User-Agent / polite pool

CrossRef recommends identifying your client with a contact email:

| Variable | Header value |
|----------|--------------|
| `RA_CROSSREF_MAILTO` | `ResearchAssistant/1.0 (mailto:you@example.com)` |
| `CROSSREF_MAILTO` | Alias for the above |

Without mailto, requests use `ResearchAssistant/1.0` — functional but lower polite-pool priority.

### Example request

```http
GET https://api.crossref.org/works?query=transformer+attention&rows=8
User-Agent: ResearchAssistant/1.0 (mailto:you@example.com)
```

## Normalization

CrossRef work items map to `RetrievedPaper`:

| CrossRef field | `RetrievedPaper` field |
|----------------|------------------------|
| `title[]` | `title` (first element) |
| `abstract` | `abstract` (HTML stripped) |
| `published-print` / `published-online` / `issued` | `year` |
| `container-title[]` | `venue` |
| `URL` or DOI link | `url` |
| `DOI` | `doi` |
| `author[]` | `authors` (given + family) |

## Configuration

```yaml
retrieval:
  providers:
    crossref:
      enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__CROSSREF__ENABLED=true
RA_CROSSREF_MAILTO=you@example.com
```

!!! tip "Always set mailto"
    CrossRef polite pool improves reliability under load. Set `RA_CROSSREF_MAILTO` before enabling this provider in production or batch jobs.

## Health check

Query with `rows=1`, 15s timeout.

## Operational notes

- Strong for DOI resolution and publisher metadata; abstracts may be missing for some records
- Pairs well with OpenAlex (coverage) and arXiv (recent preprints)
- 429 handling matches Semantic Scholar — automatic backoff

See also: [Provider matrix](../provider-matrix.md), [Environment variables](../../configuration/environment-variables.md).
