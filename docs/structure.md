# Folder Structure

This repository is organized around two independent version axes:

- case-set version
- SDK version

That separation is intentional.

## Top Level

- `cases/`
  Authored prompts, rubrics, and expected outputs.
- `sdk/`
  Copied snapshots of installed SDK skill source.
- `docs/`
  Repository documentation.
- `reports/`
  Derived summaries and leaderboards.
- `runs/`
  Outputs from actual agent/model executions.
- `scripts/`
  Local utilities for populating SDK snapshots and running evaluations.

## `cases/`

- `cases/general/`
  Optional bucket for prompts not owned by one skill.
- `cases/v1/`
  First authored case-set version.
- `cases/v2/`
  SDK 4.x case-set track, created after the `mainsequence==4.4.5` skill-bundle change.

## `cases/<case-set-version>/`

- `manifest.yaml`
  Metadata for the authored case-set version.
- `skills/`
  One folder per skill path with reusable authored cases.

## `cases/<case-set-version>/skills/<skill-path>/`

- `README.md`
  Human explanation for the authored case bank for that skill.
- `skill.yaml`
  Case-set metadata for that skill.
- `cases/`
  The actual reusable authored cases.

## `sdk/<sdk-version>/`

- `manifest.json`
  Inventory of the copied installed SDK bundle.
- `source-of-truth.yaml`
  Auditable upstream source reference for the copied SDK snapshot. This records
  the public git repository, tag/ref, commit, verification status, and the local
  snapshot path being evaluated.
- `case-map.yaml`
  Declares which case-set version each skill should use for this SDK version.
- `agent_scaffold/AGENTS.md`
  Copied top-level scaffold instructions from the installed package.
- `skills/`
  One folder per copied installed skill path.

## `sdk/<sdk-version>/skills/<skill-path>/`

- `README.md`
  Human explanation for the SDK snapshot folder.
- `skill.yaml`
  Snapshot metadata for that copied skill.
- `source/SKILL.md`
  Exact copied skill instructions from the installed package.

## Case Skill Folder vs SDK Skill Folder

The folder names intentionally mirror each other:

```text
cases/<case-set-version>/skills/<skill-path>/
sdk/<sdk-version>/skills/<skill-path>/
```

They do not mean the same thing.

- `cases/<case-set-version>/skills/<skill-path>/`
  Contains authored evaluation material: case-bank README, prompts, expected answers, rubrics, and expected artifacts.
- `sdk/<sdk-version>/skills/<skill-path>/`
  Contains copied SDK material: snapshot metadata and `source/SKILL.md`.

The case folder should not contain a copy of `SKILL.md`. The SDK skill source is selected by `sdk/<sdk-version>/case-map.yaml` and injected by the runner when a case executes.

The upstream source of truth is selected by `sdk/<sdk-version>/source-of-truth.yaml`.
This file is version-level metadata. Individual cases should reference copied
SDK skill paths through `supporting_context`. Implementation-derived cases
should use `case_source_of_truth` for the evaluated repository, package version,
ref, files, and symbols.

## `runs/sdk/<sdk-version>/<agent>/<model>/<timestamp>/`

- `manifest.json`
  Metadata for one run.
- `skills/`
  Skill-specific outputs for that run.
- `evaluations/`
  Scores and rubric results.
- `logs/`
  Raw request/response and execution logs.

## Why This Structure Is Better

With this structure:

- adding `sdk/3.17.39/` does not force copying `cases/v1/`
- a skill can keep using `v1` for several SDK versions
- only the mapping file changes when compatibility changes but the authored case bank does not
- a major SDK skill-bundle change can move the new SDK map to `v2` while preserving `v1` history

That keeps the repo smaller and makes SDK drift explicit instead of hidden in duplicate folders.
