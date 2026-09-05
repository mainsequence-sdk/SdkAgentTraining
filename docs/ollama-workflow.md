# Ollama Workflow

Ollama is the initial DSPy provider binding. It is configured independently for
the case builder, solver, and judge in `workspace.yaml`:

```yaml
model:
  provider: ollama
  name_env: MS_AGENT_EVAL_SOLVER_MODEL
  endpoint_env: OLLAMA_BASE_URL
  parameters:
    temperature: 0.2
```

Set runtime values beside the workspace in an ignored `.env`:

```dotenv
OLLAMA_BASE_URL=http://127.0.0.1:11434
MS_AGENT_EVAL_CASE_BUILDER_MODEL=builder-model
MS_AGENT_EVAL_SOLVER_MODEL=solver-model
MS_AGENT_EVAL_JUDGE_MODEL=judge-model
```

All three model names must resolve to different identities. Reusing the solver
as judge, builder as solver, or any other role equality is a preflight error.

The provider constructs an observed `dspy.LM` directly. There is no parallel
raw chat API. DSPy's typed adapter renders requests; the observer stores the
final rendered messages, provider response, usage, latency, configured cost,
role, and model identity under the external data root. DSPy cache and LiteLLM
retries are disabled so framework budgets and call evidence remain
authoritative.

Check identities before calling a model:

```bash
uv run ms-agent-eval inspect \
  --workspace /path/to/workspace.yaml
```

Then use the builder, baseline, or optimization commands described in
[Getting started](getting-started.md). Builder, solver, and judge usage is
reported separately; optimization cannot hide judge cost inside solver cost.
