# Training Conventions

## Core principle

Keep the reusable corpus separate from generated results.

- `cases/general/` is optional and only for prompts that are not tied to one skill
- `cases/skills/` is for general skill cases that are not pinned to one SDK version
- `cases/sdk/<version>/` is the versioned seed copied from the installed library
- `runs/` stores outputs from a specific agent, model, and SDK version

## Case layout

Each concrete case should live in its own folder:

```text
cases/sdk/<version>/skills/<skill-path>/cases/<case-id>/
├── case.yaml
├── prompt.md
├── expected/
│   ├── response.md
│   └── artifacts/
└── rubric.yaml
```

Recommended `case.yaml` fields:

- `id`
- `title`
- `skill_path`
- `tags`
- `difficulty`
- `requires`
- `success`

Recommended `rubric.yaml` fields:

- `passing_score`
- `criteria`
- `notes`

## Skill-specific cases

Use `cases/skills/<skill-path>/` for reusable skill cases that should not live under a single SDK version.

Use `cases/sdk/<version>/skills/` for version-pinned skill cases and copied source material.

Use the exact SDK skill path under `cases/sdk/<version>/skills/`, for example:

- `cases/sdk/3.17.33/skills/project_builder/...`
- `cases/sdk/3.17.33/skills/command_center/workspace_builder/...`

The population script creates, per installed SDK version:

- `manifest.json`
- `agent_scaffold/AGENTS.md`
- `skills/<skill>/skill.yaml`
- `skills/<skill>/source/SKILL.md`
- `skills/<skill>/cases/`

That gives each installed skill a versioned home before prompts are added.

## Run layout

Each execution goes under:

```text
runs/sdk/<sdk-version>/<agent>/<model>/<timestamp>/
```

Recommended contents:

```text
manifest.json
skills/
evaluations/
logs/
```

Store one `response.md`, artifact set, and evaluation file per executed case inside that run folder.
