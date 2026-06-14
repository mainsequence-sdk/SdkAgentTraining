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
- `case_source_of_truth` when the case is derived from real implementation files
- `supporting_context` for SDK skill snapshots, planning docs, and evaluator specs

`case_source_of_truth` must point to a git repository, package version, and
repository tag/ref for the implementation being evaluated, plus
repository-relative source files and, when possible, symbols. Do not use local
checkout paths, docs, or SDK skill instructions as the case source of truth for
implementation-derived cases. Docs and SDK skill instructions belong in
`supporting_context`.

## SDK Snapshot Layout

Each installed SDK snapshot lives under:

```text
sdk/<sdk-version>/
├── manifest.json
├── source-of-truth.yaml
├── case-map.yaml
├── agent_scaffold/AGENTS.md
└── skills/<skill-path>/source/SKILL.md
```

The snapshot should contain copied source and mapping metadata only.

`source-of-truth.yaml` is required for auditable snapshots. It should identify:

- public git repository
- git ref or tag
- resolved commit SHA when verified
- verification status and method
- local copied snapshot root

Do not store authored cases under `sdk/<sdk-version>/`.

Do not store copied SDK `SKILL.md` files under `cases/<case-set-version>/`.

Use this ownership rule:

- `cases/<case-set-version>/skills/<skill-path>/`
  Authored case-bank material only.
- `sdk/<sdk-version>/skills/<skill-path>/source/SKILL.md`
  Exact copied SDK skill source only.

## Case Mapping

Compatibility is declared in:

```text
sdk/<sdk-version>/case-map.yaml
```

Recommended shape:

```yaml
sdk_version: 4.4.5
source_of_truth_file: source-of-truth.yaml
default_case_set: v2
skills:
  platform_operations/orchestration_and_releases:
    case_set: v2
  data_publishing/data_nodes:
    case_set: v2
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
