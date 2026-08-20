# Ollama Provider Workflow

Ollama is an optional provider binding, not a framework default. The evaluated
target and cases are selected by an experiment lock; the provider does not read
an installed target package or write into `runs/`.

## Configuration

Commit only a credential-free provider example:

```yaml
schema_version: 1
id: local-ollama.example
driver: ollama
model: model-name
parameters:
  base_url_env: OLLAMA_BASE_URL
  temperature: 0.0
  timeout_seconds: 300
```

Set runtime values outside Git:

```bash
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export OLLAMA_MODEL=model-name
export MS_AGENT_EVAL_DATA_ROOT=/absolute/path/outside/the/repository
```

`OllamaProvider` validates a credential-free HTTP(S) endpoint, sends the exact
`/api/chat` payload for raw programs, normalizes token usage, and exposes an
observed DSPy binding. Rendered messages plus request/response bodies are stored
through the external artifact store. DSPy cache and LiteLLM retries are disabled
so framework lifecycle/budget policy remains authoritative.

## Raw versus DSPy

Use the same locked case, snapshot, model, and parameters for comparisons:

- raw programs preserve exact message templates and are the replay/control arm;
- DSPy programs use the typed `InstructionResponse` signature and observed chat
  adapter;
- the report must retain distinct engine/program/adapter identities.

DSPy optimization is a different experiment. It cannot compile while running a
benchmark and cannot access test/challenge cases until candidate publication.

## Live acceptance

Contract tests use a deterministic transport and require no server. To exercise a
real configured model:

```bash
OLLAMA_BASE_URL=http://127.0.0.1:11434 \
OLLAMA_MODEL=model-name \
uv run pytest -m ollama
```

Until both raw and DSPy live calls pass and their captured payloads are reviewed,
the provider remains opt-in rather than production-accepted. No fixed LAN URL,
model name, or relabelable evaluator identity is embedded in the framework.
