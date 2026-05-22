# Contributing

Thank you for improving the AI Research Assistant. This file is the **canonical contributor entry** for GitHub — the docs site links here rather than duplicating it.

**Full documentation:** https://ndevu12.github.io/Research_Assistant_Model/

## Code contributions

### Setup

```bash
pipenv install --dev
pipenv run pytest
```

See the docs site for [local development setup](https://ndevu12.github.io/Research_Assistant_Model/development/local-setup/) and [testing](https://ndevu12.github.io/Research_Assistant_Model/development/testing/).

### Guidelines

1. Run `pipenv run pytest -m "not slow"` before opening a PR.
2. Match existing import and module layout — see [import conventions](https://ndevu12.github.io/Research_Assistant_Model/development/import-conventions/).
3. Keep changes focused; avoid unrelated refactors in the same PR.
4. Add or update tests when behavior changes.

## Documentation contributions

Documentation is published with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/) from the `docs/` directory.

### Local preview

```bash
pipenv install --dev
pipenv run mkdocs serve
# → http://127.0.0.1:8000/Research_Assistant_Model/
```

Build without serving (same checks as CI):

```bash
pipenv run mkdocs build --strict
pipenv run python scripts/check_docs_policy.py
```

### File location policy

| Location | Role |
|----------|------|
| Root `README.md`, `contributing.md` | GitHub landing and contributor entry — **stay at repo root** |
| `docs/` | Deep, code-backed reference pages for the docs site |
| `docs/contributing.md` | Short pointer to this file only |

**Do:** write new deep content in `docs/` from code analysis; link getting-started pages to the root README for copy-paste commands.

**Do not:** move or gut root README/contributing; copy-paste README body into docs pages; ship scaffold placeholders (CI rejects them).

### Writing conventions

1. **Reference pattern:** Docs pages link to the root README for quick-start commands; add internals and analysis below the link.
2. **Admonition types:** `warning` for stubs/known bugs, `tip` for cookbooks, `info` for defaults.
3. **Code paths:** Use `pipenv run python -m src` in examples.
4. **Config examples:** Show YAML + equivalent `RA_*` env override side-by-side.
5. **Mermaid:** Use for pipeline/LLM diagrams; keep node IDs camelCase.
6. **Status tags:** Mark API and stub providers as experimental or planned.

Authoritative references:

| Topic | Docs page |
|-------|-----------|
| Canonical sources (command blocks, warnings) | [reference/canonical-sources.md](https://ndevu12.github.io/Research_Assistant_Model/reference/canonical-sources/) |
| Known issues | [quality/known-issues.md](https://ndevu12.github.io/Research_Assistant_Model/quality/known-issues/) |
| Setup system | [setup-system/index.md](https://ndevu12.github.io/Research_Assistant_Model/setup-system/) |
| Publishing / CI | [development/publishing.md](https://ndevu12.github.io/Research_Assistant_Model/development/publishing/) |
| Environment variables | [configuration/environment-variables.md](https://ndevu12.github.io/Research_Assistant_Model/configuration/environment-variables/) |

The legacy file `docs/research-quality-known-issues.md` is a redirect only; edit `docs/quality/known-issues.md`.
