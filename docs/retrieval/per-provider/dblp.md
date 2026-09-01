# DBLP

DBLP is the authoritative computer-science bibliography: precise titles,
venues, years, and DOIs, but no abstracts. Disabled by default — enable it
for computer-science queries where venue accuracy matters.

Implementation: `src/retrieval/providers/dblp.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://dblp.org/search/publ/api` |
| Query params | `q`, `format=json`, `h` (limit) |
| Authentication | None |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |
| Rate limiting | HTTP 429 → sleep `Retry-After` |

## Normalization

DBLP hit records map to `RetrievedPaper`:

| DBLP field | `RetrievedPaper` field |
|------------|------------------------|
| `info.title` | `title` (trailing period stripped) |
| `info.year` | `year` |
| `info.venue` | `venue` |
| `info.ee` / `info.url` | `url` |
| `info.doi` | `doi` |
| `info.authors.author[]` | `authors` |

Because DBLP records carry no abstracts, papers found only through DBLP rank
lower on abstract-dependent signals; cross-provider metadata reconciliation
fills the abstract when another provider returns the same paper.

## Configuration

```yaml
# config/providers.yaml
providers:
  dblp:
    enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__DBLP__ENABLED=true
```

See also: [Provider matrix](../provider-matrix.md).
