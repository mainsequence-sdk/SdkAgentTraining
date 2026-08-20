# Getting Started

This is the shortest complete workflow: select a repository and its skills,
build cases with one LLM, solve them with a second LLM, and score them with a
third LLM.

## 1. Install Python 3.12+

```bash
uv sync --python 3.12
```

DSPy is installed with the base library; no extra is needed.

## 2. Create one workspace manifest

```bash
mkdir my-evaluation
cd my-evaluation

uv run --project /path/to/ms-agent-eval ms-agent-eval init \
  --id example-evaluation \
  --repo https://github.com/example/project \
  --ref v1.2.3 \
  --global-instructions AGENTS.md \
  --skills-directory .agents/skills \
  --cases cases
```

Use repeated `--skill-file path/to/SKILL.md` arguments instead of
`--skills-directory` for an exact list. The two forms are mutually exclusive.

`init` creates `workspace.yaml`, an empty case directory, a grouped split file,
a judge-calibration manifest, and `.env.example`. It does not clone the target
into the workspace.

## 3. Configure three distinct models

```bash
cp .env.example .env
```

Set real, different model names:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
MS_AGENT_EVAL_CASE_BUILDER_MODEL=builder-model
MS_AGENT_EVAL_SOLVER_MODEL=solver-model
MS_AGENT_EVAL_JUDGE_MODEL=judge-model
```

The endpoint may be shared, but the resolved model identity for each role must
differ. `.env` is local and ignored. If `workspace.data_root` is absent, all
generated data goes to `~/ms_agent_eval/example-evaluation`.

## 4. Build and promote cases

The first validation of a new workspace exits successfully after validating the
manifest and immutable source, and reports `status: incomplete` plus exact
readiness blockers. It does not create an experiment lock or make a model call.
Build external drafts:

```bash
uv run --project /path/to/ms-agent-eval ms-agent-eval cases build \
  --workspace workspace.yaml \
  --coverage "Create grounded cases covering every discovered skill"
```

This resolves the repository tag to a commit, creates/reuses an immutable
external snapshot, invokes the configured DSPy case builder once per selected
skill, validates its output, and stores call evidence plus drafts externally.
It does not modify `cases/`.

Inspect and promote accepted drafts:

```bash
uv run --project /path/to/ms-agent-eval ms-agent-eval cases inspect-drafts \
  --workspace workspace.yaml

uv run --project /path/to/ms-agent-eval ms-agent-eval cases promote \
  --workspace workspace.yaml \
  --draft DRAFT_ID
```

Promotion writes the case package and assigns its leakage group to exactly one
split. The package records builder model/program, snapshot, request, and content
hashes; a direct edit invalidates provenance.

## 5. Add human-labelled judge calibration

`judge-calibration/manifest.yaml` must contain candidate responses labelled at
least `strong`, `partial`, `incorrect`, `contradictory`, and `adversarial`.
Every fixture references a promoted case and declares its human-accepted score
range. The LLM judge must pass this corpus before any solver request is made.

```yaml
schema_version: 2
fixtures:
  - id: strong-example
    case: case-id
    candidate: strong.md
    label: strong
    score_range: [0.9, 1.0]
```

## 6. Validate and inspect

```bash
uv run --project /path/to/ms-agent-eval ms-agent-eval validate \
  --workspace workspace.yaml

uv run --project /path/to/ms-agent-eval ms-agent-eval inspect \
  --workspace workspace.yaml
```

`inspect` shows the resolved commit, snapshot hash, selected instruction files,
discovered skill ids, case/split coverage, all three DSPy program and model
identities, calibration identity, runtime, projected calls, and immutable
experiment lock hashes before a scored run.

## 7. Evaluate, then optimize separately

```bash
uv run --project /path/to/ms-agent-eval ms-agent-eval run baseline \
  --workspace workspace.yaml

uv run --project /path/to/ms-agent-eval ms-agent-eval run optimize-few-shot \
  --workspace workspace.yaml
```

The baseline solves and judges promoted cases. Optimization sees only train and
development cases, compiles state-only DSPy JSON, publishes that artifact, and
only then loads the untouched test split for final evaluation. Solver and judge
usage are budgeted and reported separately.

All run output paths printed by the commands are under the external data root.
