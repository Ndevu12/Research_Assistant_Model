# PubMed

PubMed indexes biomedical and life-science literature via NCBI. Disabled by
default — enable it for biomedical queries.

Implementation: `src/retrieval/providers/pubmed.py`

## HTTP API

| Attribute | Value |
|-----------|-------|
| Search URL | `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi` |
| Fetch URL | `GET https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi` |
| Query params | `db=pubmed`, `term`, `retmax`, `sort=relevance` |
| Authentication | `NCBI_API_KEY` (optional; raises rate limits) |
| Timeout | 60s (search), 15s (health) |
| Retries | 3 with exponential backoff |
| Rate limiting | HTTP 429 → sleep `Retry-After` |

Search is a two-step flow: `esearch` returns relevance-sorted PMIDs, then a
single `efetch` call hydrates all of them as XML — including abstracts,
which NCBI's JSON `esummary` endpoint does not provide.

## Normalization

`PubmedArticle` XML records map to `RetrievedPaper`:

| PubMed field | `RetrievedPaper` field |
|--------------|------------------------|
| `ArticleTitle` | `title` |
| `Abstract/AbstractText[]` | `abstract` (sections joined) |
| `Journal/JournalIssue/PubDate/Year` | `year` |
| `Journal/Title` | `venue` |
| PMID article page | `url` |
| `ELocationID[@EIdType="doi"]` | `doi` |
| `AuthorList/Author` | `authors` (fore + last name) |
| `KeywordList/Keyword` | `keywords` |

## Configuration

```yaml
# config/providers.yaml
providers:
  pubmed:
    enabled: true
```

```bash
RA_RETRIEVAL__PROVIDERS__PUBMED__ENABLED=true
NCBI_API_KEY=...   # optional
```

See also: [Provider matrix](../provider-matrix.md).
