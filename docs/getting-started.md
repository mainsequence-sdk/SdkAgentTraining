# Getting Started

This guide runs a complete evaluation locally: it loads an experiment
workspace, validates its authored suite and trusted evaluator, reads a saved LLM
response, applies the case rubric, and emits a structured score. It requires no
network, Docker daemon, model server, or MainSequence installation.

## 1. Install the project

From the repository root:

```bash
uv sync --python 3.12
```

Confirm the workspace is internally consistent:

```bash
uv run ms-agent-eval config validate \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

This loads both suite versions, every indexed case, their grouped splits,
compatibility mappings, programs, runtimes, storage, plans, and evaluator
profiles.

## 2. Validate the evaluator

```bash
uv run ms-agent-eval evaluator validate mainsequence-rules-v1 \
  --suite mainsequence-agent-skills-v2 \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

The command calibrates the trusted evaluator against its positive, negative,
and adversarial fixtures, then confirms that every active case resolves to an
exact registered evaluator name and method.

## 3. Score an LLM response

Use the included ideal response for a deterministic first run:

```bash
uv run ms-agent-eval evaluator score mainsequence-rules-v1 \
  --suite mainsequence-agent-skills-v2 \
  --case or-001-recurring-artifact-job \
  --response experiments/mainsequence-sdk/evaluators/mainsequence/calibration/ideal.md \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

The result includes:

```json
{
  "case_id": "or-001-recurring-artifact-job",
  "passed": true,
  "score": 1.0,
  "status": "evaluated"
}
```

To evaluate a real model response, save its text outside the Git repository and
replace the `--response` path. The authored prompt is at:

```text
experiments/mainsequence-sdk/suites/v2/units/platform_operations/
  orchestration_and_releases/cases/or-001-recurring-artifact-job/prompt.md
```

## 4. Configure external experiment storage

Snapshotting targets and creating experiment runs require a machine-local data
root outside this repository:

```bash
cp experiments/mainsequence-sdk/.env.example \
  experiments/mainsequence-sdk/.env
```

Edit `.env` and set an absolute external path:

```dotenv
MS_AGENT_EVAL_DATA_ROOT=/absolute/path/outside/this/repository/mainsequence-sdk
```

Resolution order is:

1. `--data-root` on the command line;
2. the process environment;
3. `.env` beside `workspace.yaml`.

The real `.env` is ignored. Only `.env.example` is committed.

## 5. Plan the DSPy optimization experiment

Planning is deterministic and makes no model request:

```bash
uv run ms-agent-eval experiment plan mainsequence-v2-few-shot-readiness \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

The lock identifies the target commit, source snapshot, suite and case bytes,
protected split, program, provider, runtime, evaluator implementation and
calibration bytes, optimizer, and storage profile.

The current MainSequence optimization plan intentionally fails evaluator
preflight before any model call because most train/development cases do not yet
have calibrated automatic evaluators. This prevents a misleading optimized
score. The offline scoring workflow above is fully operational for the active
calibrated case.

## Next steps

- Use [Target source workflow](target-source-workflow.md) to resolve and snapshot
  another GitHub repository.
- Use [Ollama workflow](ollama-workflow.md) to configure local model calls.
- Read [Repository structure](structure.md) before creating another experiment
  workspace.
