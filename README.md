# SDK Agent Training

This repository stores authored evaluation cases, SDK snapshots, and recorded runs for testing the `agent_scaffold` skills bundled with the public `mainsequence` library.

The structure separates three concerns:

- `cases/`: authored case sets, versioned independently from the SDK
- `sdk/`: copied snapshots of the installed `mainsequence` / `agent_scaffold` bundle
- `runs/`: model outputs grouped by SDK version, agent, and model

## Layout

```text
SdkAgentTraining/
├── cases/
│   ├── general/
│   └── v1/
│       ├── manifest.yaml
│       └── skills/
│           └── <skill-path>/
│               ├── README.md
│               ├── skill.yaml
│               └── cases/
│                   └── <case-id>/
├── sdk/
│   └── <sdk-version>/
│       ├── manifest.json
│       ├── case-map.yaml
│       ├── agent_scaffold/
│       │   └── AGENTS.md
│       └── skills/
│           └── <skill-path>/
│               ├── README.md
│               ├── skill.yaml
│               └── source/
│                   └── SKILL.md
├── docs/
├── reports/
├── runs/
│   └── sdk/<sdk-version>/<agent>/<model>/<timestamp>/
└── scripts/
```

## Folder Purpose

- `cases/general/`
  Optional cross-cutting prompts not owned by one skill.
- `cases/v1/`
  The first authored case-set version.
- `cases/v1/skills/<skill-path>/cases/`
  The actual reusable prompt cases.
- `sdk/<sdk-version>/`
  Snapshot of the installed SDK bundle for one library version.
- `sdk/<sdk-version>/case-map.yaml`
  Compatibility map from SDK skill path to authored case-set version.
- `sdk/<sdk-version>/skills/<skill-path>/source/SKILL.md`
  Exact copied skill text from the installed library.
- `runs/sdk/<sdk-version>/<agent>/<model>/<timestamp>/`
  One concrete execution run for one SDK version, agent, and model.

## Why This Split Exists

The authored case bank should not be duplicated every time the SDK changes.

The intended workflow is:

1. keep authored cases under `cases/v1/...`
2. snapshot each installed SDK under `sdk/<version>/...`
3. declare compatibility in `sdk/<version>/case-map.yaml`

That means a small SDK change usually requires:

- a new SDK snapshot
- maybe an updated compatibility map

and not a full duplicate of the authored case bank.

## Setup

```bash
uv sync
uv run python scripts/populate_training_skills.py
```

The population script has no arguments. It reads the installed `mainsequence` and `agent_scaffold` packages and refreshes:

- `sdk/<installed-version>/`
- `sdk/<installed-version>/case-map.yaml`

## Workflow

1. Refresh the installed SDK snapshot with `scripts/populate_training_skills.py`.
2. Author or update reusable cases under `cases/v1/skills/<skill-path>/cases/`.
3. Adjust `sdk/<sdk-version>/case-map.yaml` only when a skill should map to a different case-set version.
4. Run agents against a case id; the runner resolves the installed SDK version, loads the mapped case set, and injects the matching copied `AGENTS.md` and `SKILL.md`.
5. Store outputs and evaluation artifacts under `runs/sdk/<sdk-version>/...`.

## Useful Commands

```bash
uv run python scripts/populate_training_skills.py
uv run python scripts/create_run.py --agent codex --model gpt-5.4
uv run python scripts/run_ollama_case.py --model ms-fast:latest --case or-001-recurring-artifact-job
```

See [docs/conventions.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/conventions.md) for the case and run format, [docs/structure.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/structure.md) for the folder-by-folder explanation, and [docs/sdk-cli-notes.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/sdk-cli-notes.md) for the SDK/CLI snapshot rules.
See [docs/ollama-workflow.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/ollama-workflow.md) for the local model testing workflow.
See [docs/datanode-evaluation-spec.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/datanode-evaluation-spec.md), [docs/simpletable-evaluation-spec.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/simpletable-evaluation-spec.md), and [docs/simpletable-updater-evaluation-spec.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/simpletable-updater-evaluation-spec.md) for the construction evaluation criteria.
