# Training Conventions

## Core Principle

Keep authored cases separate from copied SDK source.

- `cases/` holds authored case sets
- `sdk/` holds copied library snapshots
- `sdk/<version>/case-map.yaml` declares which case set a skill uses for that SDK version
- `runs/` holds generated outputs

## Case-Set Layout

Each case-set version lives under:

```text
cases/<case-set-version>/
├── manifest.yaml
└── skills/
    └── <skill-path>/
        ├── README.md
        ├── skill.yaml
        └── cases/
            └── <case-id>/
```

Each concrete case should live in its own folder:

```text
cases/<case-set-version>/skills/<skill-path>/cases/<case-id>/
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
- `case_set_version`
- `authored_against_sdk_version`
- `tags`
- `difficulty`
- `requires`
- `success`

## SDK Snapshot Layout

Each installed SDK snapshot lives under:

```text
sdk/<sdk-version>/
├── manifest.json
├── case-map.yaml
├── agent_scaffold/AGENTS.md
└── skills/<skill-path>/source/SKILL.md
```

The snapshot should contain copied source and mapping metadata only.

Do not store authored cases under `sdk/<sdk-version>/`.

## Case Mapping

Compatibility is declared in:

```text
sdk/<sdk-version>/case-map.yaml
```

Recommended shape:

```yaml
sdk_version: 3.17.38
default_case_set: v1
skills:
  platform_operations/orchestration_and_releases:
    case_set: v1
  data_publishing/simple_tables:
    case_set: v1
```

This allows:

- one authored case bank to serve multiple SDK versions
- skill-by-skill remapping when a newer SDK needs a newer case-set version

## Run Layout

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
