# OpenAlex

OpenAlex is the primary bibliographic index provider — enabled by default and used in both the CLI shortcut path and the full pipeline.

Implementation: `src/retrieval/providers/openalex.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://api.openalex.org/works` |
| Query params | `search=<query>`, `per-page=<limit>` |
| Authentication | None required |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |

### Example request

```http
GET https://api.openalex.org/works?search=transformer+attention&per-page=8
```

No API key or mailto is required. OpenAlex is suitable for broad scholarly coverage including DOIs, venues, and citation counts.

## Normalization

OpenAlex work JSON maps to `RetrievedPaper`:

| OpenAlex field | `RetrievedPaper` field |
|----------------|------------------------|
| `display_name` | `title` |
| `abstract_inverted_index` | `abstract` (reconstructed) |
| `publication_year` | `year` |
| `primary_location.source.display_name` | `venue` |
| `id` or landing page URL | `url` |
| `doi` | `doi` |
| `cited_by_count` | `citation_count` |

Full raw JSON is preserved in `raw_metadata`.

## Configuration

**Default:** enabled in `config/default.yaml` and `config/providers.yaml`.

```yaml
retrieval:
  providers:
    openalex:
      enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__OPENALEX__ENABLED=true
RA_RETRIEVAL__PER_PROVIDER_LIMIT=10
```

## Health check

`_ping()` issues a minimal `per-page=1` query against the works endpoint. Used by setup health checks when retrieval providers are validated.

## Operational notes

- No explicit 429 handler — relies on retry + backoff
- Rate limits are generous for polite use; avoid tight loops in batch scripts
- OpenAlex IDs (`https://openalex.org/W...`) are used as paper URLs when no landing page exists

See also: [Provider matrix](../provider-matrix.md), [Retrieval overview](../overview.md).
