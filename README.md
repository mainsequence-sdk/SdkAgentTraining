# MS Agent Eval

MS Agent Eval is a Python 3.12+ library for reproducible evaluation and
optimization of prompts/instruction bundles from arbitrary GitHub repositories.
The evaluated repository is configuration, not a framework dependency.

The repository contains two kinds of version-controlled material:

- the reusable `ms_agent_eval` library under `src/`;
- first-party experiment workspaces under `experiments/`.

Clones, extracted snapshots, model responses, evaluations, compiled DSPy state,
container evidence, reports, and metadata databases live under a configured
external data root and must not be committed here.

## Architecture

```text
GitHub URL + tag/commit
          │ resolve tag to immutable commit
          ▼
external content-addressed snapshot
          │ exact configured AGENTS/skill paths
          ▼
suite + compatibility + grouped split + program/provider/runtime
          │ immutable experiment lock
          ▼
raw or DSPy model program ── optional isolated Docker target execution
          │ rendered-call evidence
          ▼
calibrated exact-name evaluator
          │
          ├── external benchmark/report artifacts
          └── DSPy metric projection for a separate optimization experiment
```

DSPy is canonical for newly authored declarative model programs. The raw engine
remains first-class for exact prompt replay and causal controls. Optimization is
never an implicit benchmark step: it sees only train/development data, publishes
a state-only JSON candidate, and is validated on untouched test/challenge data
before explicit promotion.

## Library modules

- `ms_agent_eval.core`: neutral schemas, planning, sources, snapshots, storage,
  lifecycle, Docker execution, evaluation, legacy export, and reporting.
- `ms_agent_eval.programs.raw`: exact configurable system/user rendering.
- `ms_agent_eval.programs.dspy`: typed DSPy program, observed LM, authoritative
  metric adapter, budgets, protected splits, compilation, and promotion.
- `ms_agent_eval.providers.ollama`: optional Ollama raw/DSPy bindings.
- `ms_agent_eval.core.evaluator_plugins`: explicit loading of trusted evaluator
  code owned by an experiment workspace.

The Main Sequence experiment workspace is only a proof target. Its evaluator is
under `experiments/mainsequence-sdk/evaluators/`, outside the installed library.
Another repository can provide its own GitHub source, exact instruction roots,
suites, programs, providers, evaluators, and runtimes without changing library
code.

## Repository Layout

```text
.agents/                     repository-local authoring workflows
src/ms_agent_eval/           one installable library
experiments/mainsequence-sdk version-controlled experiment workspace
tests/                       unit, integration, fixtures, and acceptance tests
docs/                        architecture and implementation records
```

See [structure.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/structure.md)
and [conventions.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/conventions.md).
For the fastest runnable workflow, start with
[Getting started](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/getting-started.md)
or browse the [documentation index](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/index.md).

## Setup

The baseline interpreter is CPython 3.12. `.python-version` pins that baseline.

```bash
uv sync
uv run ms-agent-eval config validate \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

The base library installs without DSPy or any evaluated target library. Add the
`dspy` extra only when compiling or running DSPy programs:

```bash
uv venv --python 3.12 /tmp/ms-agent-eval
uv pip install --python /tmp/ms-agent-eval/bin/python .
uv pip install --python /tmp/ms-agent-eval/bin/python '.[dspy]'
```

## Configure a Repository

A target declares its GitHub source and exact instruction paths. There are no
framework defaults for `agent_scaffold`, `.agents/skills`, or any other layout.

```yaml
schema_version: 1
id: example-target
display_name: Example target
source:
  type: github
  repository_url: https://github.com/example/project
  ref: {type: tag, value: v1.2.3}
instruction_bundles:
  - id: repository-guidance
    display_name: Repository guidance
    global_context:
      - id: agents
        source_path: .agents/AGENTS.md
        required: true
    units:
      sources:
        - id: skills
          type: directory
          root: .agents/skills
          locator:
            filename: SKILL.md
            recursive: true
            include: ["**/SKILL.md"]
            exclude: []
            follow_symlinks: false
          logical_id: {prefix: ""}
          allow_empty: false
```

Resolve/snapshot with an external root:

```bash
cp path/to/experiment/.env.example path/to/experiment/.env
# Edit .env with an absolute external path.

uv run ms-agent-eval target resolve example-target --workspace path/to/workspace.yaml
uv run ms-agent-eval target snapshot example-target \
  --workspace path/to/workspace.yaml \
  --data-root /optional/explicit/override
```

Data-root precedence is `--data-root`, the process environment, then the `.env`
beside `workspace.yaml`. The real `.env` is ignored because it is machine-local;
each committed experiment should provide a safe `.env.example`.

Tags are accepted as author input, but locks and runs use the resolved 40-byte
commit and content-addressed snapshot id.

## Experiments

An experiment selects target, snapshot, bundle, suite, compatibility map,
program, provider, runtime, storage, and optionally an optimizer. Planning is
pure and deterministic; creation persists the lock and resumable job state only
to the external data plane.

```bash
uv run ms-agent-eval experiment plan EXPERIMENT_ID \
  --workspace path/to/workspace.yaml

uv run ms-agent-eval experiment create EXPERIMENT_ID \
  --workspace path/to/workspace.yaml \
  --data-root "$MS_AGENT_EVAL_DATA_ROOT"
```

Repository imports, tools, tests, and patches use the pinned Python 3.12/uv
Docker executor. Response-only prompt evaluation can use the `none` runtime.
Program/provider execution is exposed through the typed package APIs so an
application can schedule workers without coupling core to a particular model.

## Evaluation and Optimization

Cases explicitly declare `active`, `manual_review_required`, or
`not_evaluable`. Active evaluator names resolve exactly through a calibrated
registry. Unsupported cases fail before a model request unless unscored
generation was explicitly allowed.

The configured Main Sequence evaluator can validate its case bank with:

```bash
uv run ms-agent-eval evaluator validate mainsequence-rules-v1 \
  --suite mainsequence-agent-skills-v2 \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

The committed Main Sequence optimization readiness experiment plans correctly
but fails evaluator preflight because most v2 train/development cases are not yet
calibrated. No model call or misleading optimized score is produced.

## Results and Reports

Generated snapshots, responses, evaluations, compiled programs, and reports are
written only below `MS_AGENT_EVAL_DATA_ROOT`. A minimal schema-v0 run fixture lives
under `tests/fixtures/legacy-run-v0/` solely to test compatibility readers.

Generic summaries and regressions are produced with `ms-agent-eval report summary`
and `ms-agent-eval report regression`. Reports never merge different commits,
splits, compiled artifacts, providers, or evaluators into one unlabeled score.

## Verification

```bash
uv run ruff check src tests
uv run pytest

# Optional live boundaries
MS_AGENT_EVAL_RUN_DOCKER_TESTS=1 uv run pytest -m docker
OLLAMA_BASE_URL=http://127.0.0.1:11434 OLLAMA_MODEL=model-name \
  uv run pytest -m ollama
```

The Docker integration is pinned and network-isolated. Live Ollama acceptance is
optional and remains unverified until an endpoint/model is configured.

For authored Main Sequence cases, use the local
[case-authoring skill](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/.agents/skills/case-authoring/SKILL.md).
For a new public Main Sequence version, use the
[MainSequence experiment-version skill](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/.agents/skills/mainsequence-experiment-version/SKILL.md).
