# AI Research Assistant

A local-first research pipeline that retrieves academic papers from multiple scholarly APIs, ranks and clusters them with embeddings, synthesizes cross-paper insights, and exports reports in several formats. Uses **Ollama** by default for fully local LLM inference, with optional **OpenAI** and **Anthropic** providers.

Built with Python 3.11+, pydantic-ai, sentence-transformers, and async I/O.

Feature list, requirements, and RAM guidance: [README](https://github.com/Ndevu12/Research_Assistant_Model#features).

!!! warning "Default quality profile"
    Synthesis and query expansion default to **heuristic mode** (`llm_enabled: false`). Reports are fast but template-driven. Enable LLM features for richer cross-paper analysis — see [Heuristic vs LLM](llm/heuristic-vs-llm.md).

## Quick links

| Section | Description |
|---------|-------------|
| [Installation](getting-started/installation.md) | Pipenv, Python 3.11+, dependencies |
| [Quick Start](getting-started/quick-start.md) | First query and auto-setup flow |
| [CLI Reference](user-guide/cli.md) | Flags, batch vs interactive mode |
| [CLI vs API](user-guide/cli-vs-api.md) | Execution paths and provider divergence |
| [Configuration](configuration/precedence.md) | Env vars, YAML, and precedence |
| [Known Issues](quality/known-issues.md) | Research quality analysis and fix backlog |
| [Architecture](architecture/overview.md) | End-to-end pipeline overview |
| [Canonical sources](reference/canonical-sources.md) | Where copy-paste commands live (link, don't duplicate) |

Install and run: [README Quick Start](https://github.com/Ndevu12/Research_Assistant_Model#quick-start).
