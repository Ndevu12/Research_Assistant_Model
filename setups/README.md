# Setup System

Automated setup utilities for AI Research Assistant with integrated logging and health checks.

## Quick Start

### Check Setup Status
```bash
python -m setups.health_check
```

### Run Full Setup
```bash
python -m setups.manager
```

### Run Setup with Custom Model
```bash
python -m setups.manager --model mistral
```

## Modules

### `health_check.py`
Validates that all setup requirements are met.

```bash
python -m setups.health_check
python -m setups.health_check --model mistral
```

### `setup.py`
Installs Python dependencies via pipenv.

```bash
python -m setups.setup
```

### `ollama.py`
Installs Ollama and configures the model.

```bash
# Install Ollama binary
python -m setups.ollama install

# Setup model
python -m setups.ollama setup
python -m setups.ollama setup --model mistral
```

### `manager.py`
Orchestrates all setup steps.

```bash
python -m setups.manager
python -m setups.manager --model mistral
```

Entry point for full setup.

## Logging

All setup operations are logged to the `logs/` directory:
- `combined_YYYYMMDD.log` - All logs
- `error_YYYYMMDD.log` - Errors and warnings
- `events_YYYYMMDD.log` - Structured events

## Python API

```python
from setups import run_setup, print_report, check_ollama_running

# Check if Ollama is running
is_running, message = check_ollama_running()

# Print health report
all_ok = print_report()

# Run full setup
success = run_setup(model_name="llama3.2:3b")
```

## Supported Models

Supported Ollama models are defined in `config/ollama_models.yaml`. Setup auto-selects
the highest-priority model that fits your RAM and disk unless you pass `--model` or
set `RA_LLM__MODEL` in your `.env` file.

```bash
# Auto-select (recommended)
python -m setups.manager

# Force a specific supported model via CLI
python -m setups.manager --model llama3.1:8b

# Or override auto-selection in .env (takes precedence over YAML config)
# RA_LLM__MODEL=llama3.1:8b

python -m setups.health_check
```

## Troubleshooting

### Setup fails with "pipenv not found"
Install pipenv:
```bash
pip install pipenv
```

### Setup fails with "Ollama not found"
Install Ollama from https://ollama.com/download

### Model pull fails
Check internet connection and try again:
```bash
python -m setups.ollama setup --model llama3.2:3b
```

### Check logs for details
```bash
tail -f logs/combined_*.log
```
