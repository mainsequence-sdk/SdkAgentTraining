# Ollama Workflow

This repository can run one training case against one Ollama model and save the result into the versioned `runs/` tree.

## Assumptions

- Ollama is reachable at `http://192.168.1.10:11434`
- the model is already installed on that Ollama server
- the case already exists under `cases/`

The runner defaults to `http://192.168.1.10:11434`. To change it, set `OLLAMA_BASE_URL` or pass `--base-url`.

## One-case workflow

Run one case against one model:

```bash
.venv/bin/python scripts/run_ollama_case.py \
  --model ms-reasoning:latest \
  --case or-001-recurring-artifact-job
```

Another model:

```bash
.venv/bin/python scripts/run_ollama_case.py \
  --model ms-fast:latest \
  --case or-001-recurring-artifact-job
```

The runner will:

1. read the installed SDK version
2. resolve the case id through `sdk/<version>/case-map.yaml`
3. load the authored case from the mapped case-set version
4. load `AGENTS.md` and the copied skill `SKILL.md` from the matching SDK snapshot
5. send the prompt to Ollama
6. create a run folder under `runs/sdk/<version>/ollama/<model>/<timestamp>/`
7. save the raw response
8. run the automatic evaluator for the case

By default, the saved evaluation records:

- evaluator name: `codex-heuristic-v1`
- evaluator kind: `rule-based`

You can override that when needed:

```bash
.venv/bin/python scripts/run_ollama_case.py \
  --model ms-reasoning:latest \
  --case or-001-recurring-artifact-job \
  --evaluator-name codex-manual-review \
  --evaluator-kind human-review
```

## Output layout

Example:

```text
runs/sdk/4.4.5/ollama/ms-reasoning-latest/2026-04-12T16-20-00Z/
├── manifest.json
├── evaluations/
│   └── or-001-recurring-artifact-job.json
├── logs/
│   └── platform_operations/orchestration_and_releases/or-001-recurring-artifact-job/
│       ├── ollama_request.json
│       └── ollama_response.json
└── skills/
    └── platform_operations/orchestration_and_releases/or-001-recurring-artifact-job/
        ├── response.md
        ├── system_prompt.md
        └── user_prompt.md
```

## What is being tested

For `or-001-recurring-artifact-job`, this is an offline response-quality test.

It checks whether the model:

- chooses `scheduled_jobs.yaml`
- uses `Artifact` correctly
- requires pinned images
- treats `--strict` carefully
- includes verification steps

It is not a live platform execution test.

## Compare multiple models

Run the same case repeatedly:

```bash
.venv/bin/python scripts/run_ollama_case.py --model ms-fast:latest --case or-001-recurring-artifact-job
.venv/bin/python scripts/run_ollama_case.py --model ms-reasoning:latest --case or-001-recurring-artifact-job
.venv/bin/python scripts/run_ollama_case.py --model deepseek-r1:32b --case or-001-recurring-artifact-job
```

Then compare the `evaluations/or-001-recurring-artifact-job.json` files under each run.

Each evaluation JSON now includes:

- `evaluator.name`
- `evaluator.kind`
- `evaluator.evaluated_at`
