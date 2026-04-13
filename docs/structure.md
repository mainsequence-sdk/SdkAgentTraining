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

That keeps the repo smaller and makes SDK drift explicit instead of hidden in duplicate folders.
