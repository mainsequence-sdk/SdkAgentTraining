# SDK Agent Training

This repository stores prompt cases, expected outputs, and recorded runs for testing the `agent_scaffold` skills bundled with the public `mainsequence` library.

The structure separates three concerns:

- `cases/`: prompt sets, seeded from the installed SDK version
- `runs/`: model outputs grouped by SDK version, agent, and model
- `reports/`: comparisons and summaries derived from runs

## Layout

```text
SdkAgentTraining/
├── cases/
│   ├── general/
│   ├── skills/
│   └── sdk/
│       └── <sdk-version>/
│           ├── manifest.json
│           ├── agent_scaffold/
│           │   └── AGENTS.md
│           └── skills/
│               └── <skill-path>/
│                   ├── README.md
│                   ├── skill.yaml
│                   ├── source/
│                   │   └── SKILL.md
│                   └── cases/
├── docs/
├── reports/
├── runs/
│   └── sdk/<sdk-version>/<agent>/<model>/<timestamp>/
└── scripts/
```

## Folder Purpose

- `cases/general/`
  Reserved for prompts that are not owned by one specific skill.
  This folder is optional and can stay empty.
- `cases/skills/`
  General skill cases that are not tied to one installed SDK version.
  Use this when you want to test a skill conceptually across versions or keep reusable prompts outside a specific version snapshot.
- `cases/sdk/<sdk-version>/`
  The main training corpus for one installed SDK version.
- `cases/sdk/<sdk-version>/manifest.json`
  Index of the copied skill bundle for that SDK version.
- `cases/sdk/<sdk-version>/agent_scaffold/AGENTS.md`
  Snapshot of the installed top-level `agent_scaffold` instructions for that version.
- `cases/sdk/<sdk-version>/skills/<skill-path>/source/SKILL.md`
  Exact installed skill text copied from the library.
- `cases/sdk/<sdk-version>/skills/<skill-path>/skill.yaml`
  Metadata for that skill in that SDK version.
- `cases/sdk/<sdk-version>/skills/<skill-path>/cases/`
  Actual prompt cases for evaluating that specific skill.
- `runs/sdk/<sdk-version>/<agent>/<model>/<timestamp>/`
  One concrete execution run for one SDK version, agent, and model.
- `reports/`
  Summaries, comparisons, and leaderboards generated from run data.
- `scripts/`
  Local helper scripts to populate versioned cases and create run folders.
- `docs/`
  Repository documentation, conventions, and structure notes.

## Setup

```bash
uv sync
uv run python scripts/populate_training_skills.py
```

The population script has no arguments. It reads the installed `mainsequence` and `agent_scaffold` packages and seeds `cases/sdk/<installed-version>/`.

## Workflow

1. Populate or refresh the versioned skill seed from the installed SDK bundle.
2. Add reusable non-version-specific skill cases under `cases/skills/<skill-path>/`.
3. Add version-specific skill cases under `cases/sdk/<sdk-version>/skills/<skill-path>/cases/`.
4. Create a versioned run folder before executing agents.
5. Store outputs and evaluation artifacts inside the run folder.

## Useful commands

```bash
uv run python scripts/populate_training_skills.py
uv run python scripts/create_run.py --agent codex --model gpt-5.4
```

See [docs/conventions.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/conventions.md) for the case and run format, and [docs/sdk-cli-notes.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/sdk-cli-notes.md) for the CLI findings that drove this scaffold.
See [docs/structure.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/structure.md) for the folder-by-folder explanation.
See [docs/ollama-workflow.md](/Users/jose/code/MainSequenceClientSide/SdkAgentTraining/docs/ollama-workflow.md) for the local model testing workflow.
