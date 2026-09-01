# CORE

CORE aggregates open-access research outputs from repositories worldwide and
exposes direct download links, making it a natural feeder for the planned
full-text pipeline. Disabled by default and requires an API key.

Implementation: `src/retrieval/providers/core_provider.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://api.core.ac.uk/v3/search/works` |
| Query params | `q`, `limit` |
| Authentication | `CORE_API_KEY` (required, Bearer token) |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |
| Rate limiting | HTTP 429 → sleep `Retry-After` |

Free API keys are issued at the CORE services portal. Without a key the
provider reports itself unhealthy, and search fails with a clear message —
which the retrieval fan-out converts into a per-provider warning rather
than a crash.

## Normalization

CORE work records map to `RetrievedPaper`:

| CORE field | `RetrievedPaper` field |
|------------|------------------------|
| `title` | `title` |
| `abstract` | `abstract` |
| `publishedDate` / `year` | `year` |
| `publisher` / `journals[0]` | `venue` |
| `downloadUrl` / `sourceFulltextUrls[0]` | `url` (direct PDF when available) |
| `doi` | `doi` |
| `authors[].name` | `authors` |
| `citationCount` | `citation_count` |

## Configuration

```yaml
# config/providers.yaml
providers:
  core:
    enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__CORE__ENABLED=true
CORE_API_KEY=...
```

See also: [Provider matrix](../provider-matrix.md).
