# Logging and Debug

<!-- canonical: debug-mode -->

The assistant writes structured logs to `logs/` and optional JSON pipeline dumps when debug mode is enabled.

Sources: `src/utils/logging_system.py`, `src/core/pipeline.py`, `src/config/settings.py`.

## Log files

On startup, `_setup_logger()` creates a dated set of rotating log files under `logs/`:

| File | Contents | Filter |
|------|----------|--------|
| `combined_YYYYMMDD.log` | All log levels | None |
| `error_YYYYMMDD.log` | Warnings and errors | `level >= WARNING` |
| `performance_YYYYMMDD.log` | Performance metrics | `is_performance=True` |
| `events_YYYYMMDD.log` | Structured events | `is_event=True` |

Files rotate at **10 MB** with **5** backups. The same messages also go to **stdout** via a console handler.

### Tail logs during a run

```bash
tail -f logs/combined_$(date +%Y%m%d).log
tail -f logs/error_$(date +%Y%m%d).log
```

### Logger API

```python
from src.utils.logging_system import logger

logger.info("Pipeline started")
logger.warning("Provider failed")
logger.log_event("retrieval", "Cache hit", extra_data={"key": "..."})
logger.log_performance("synthesis", duration_ms=4500, success=True)
```

## Enabling debug mode

Debug is active when **either** flag is set:

| Variable | Values | Source |
|----------|--------|--------|
| `RA_PIPELINE__DEBUG` | `true` / `false` | `pipeline.debug` |
| `RA_DEBUG` | `1`, `true`, `yes` | Direct env check in `debug_enabled` property |

```bash
RA_PIPELINE__DEBUG=true
# or
RA_DEBUG=1
```

!!! warning "`.env.example` ships with debug on"
    Fresh copies of `.env.example` set `RA_DEBUG=1`. Comment it out for production-like runs unless you want debug dumps every time.

## Pipeline debug dumps

When `settings.debug_enabled` is true, after each pipeline run `ResearchPipeline._write_debug_dump()` writes:

```
logs/debug/pipeline_<session_id>_<timestamp>.json
```

The JSON contains `PipelineContext.to_debug_dict()`:

- Session ID and query
- Per-stage results (duration, partial flag, warnings, metrics)
- Artifact snapshots (ranked papers, synthesis, gap analysis, etc.)
- Configuration effective at run time

Use these dumps to inspect why a stage was partial or what papers were retrieved before deduplication.

### Debug walkthrough

1. **Enable debug:**

   ```bash
   export RA_PIPELINE__DEBUG=true
   pipenv run python -m src "your query"
   ```

2. **Run a query** (interactive or batch).

3. **Find the dump:**

   ```bash
   ls -lt logs/debug/ | head
   ```

4. **Inspect stage results:**

   ```bash
   jq '.stage_results.retrieval' logs/debug/pipeline_*.json
   jq '.artifacts.ranked_papers | length' logs/debug/pipeline_*.json
   ```

5. **Check warnings** for partial stages:

   ```bash
   jq '[.stage_results[] | select(.partial)] | keys' logs/debug/pipeline_*.json
   ```

6. **Correlate with combined log** using timestamps and session ID in log lines.

## What debug does *not* include

- Raw HTTP response bodies from retrieval providers (only normalized papers in artifacts)
- Full LLM prompts (check synthesis stage metrics/logs)
- Automatic log level change — debug dumps are additive; log level stays at INFO unless you configure logging separately

## Related settings

| Setting | Effect |
|---------|--------|
| `RA_PIPELINE__STREAM_PROGRESS` | Live Rich UI on stderr (separate from file logging) |
| `RA_PIPELINE__CONTINUE_ON_STAGE_FAILURE` | Failed stages log errors then recover heuristically |

See also: [Progress streaming](progress-streaming.md), [Troubleshooting](troubleshooting.md), [Stage toggles](../configuration/stage-toggles.md).
