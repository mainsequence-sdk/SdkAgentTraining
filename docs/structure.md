# Folder Structure

This repository is organized around one question:

How effective are the installed `agent_scaffold` skills for a specific `mainsequence` SDK version?

## Top level

- `cases/`
  Training and evaluation inputs.
- `docs/`
  Documentation for how the repository is organized and used.
- `reports/`
  Derived summaries, comparisons, and leaderboards.
- `runs/`
  Outputs from actual agent/model executions.
- `scripts/`
  Local utilities that populate versioned cases and create run folders.

## `cases/`

- `cases/general/`
  Optional bucket for prompts that are not owned by one skill.
  Example use: testing routing across multiple skills.
  It is valid for this folder to be empty.
- `cases/skills/`
  General skill cases that are not bound to a specific installed SDK version.
  Use this for reusable prompts for a skill when you do not want to duplicate them under each version yet.
- `cases/sdk/`
  The real corpus root for this repository.
  Everything here is grouped by installed SDK version.

## `cases/sdk/<sdk-version>/`

- `manifest.json`
  Inventory of the installed bundle copied for this SDK version.
- `agent_scaffold/AGENTS.md`
  Top-level scaffold instructions copied from the installed package.
- `skills/`
  One folder per installed skill path.

## `cases/sdk/<sdk-version>/skills/<skill-path>/`

- `source/SKILL.md`
  Exact skill instructions copied from the installed package.
- `skill.yaml`
  Metadata about the skill for that version.
- `cases/`
  Prompt cases used to evaluate that specific skill.

## `runs/sdk/<sdk-version>/<agent>/<model>/<timestamp>/`

- `manifest.json`
  Metadata for one run.
- `skills/`
  Skill-specific outputs for that run.
- `evaluations/`
  Scores or rubric results.
- `logs/`
  Execution notes or raw logs.

## Why `general`, `skills`, and versioned skill folders all exist

- `cases/general/` is optional and cross-cutting.
- `cases/skills/` is general but still skill-owned.
- `cases/sdk/<version>/skills/...` is the main evaluation surface.

If you do not want cross-cutting prompt sets, leave `cases/general/` empty.
If you do not want reusable non-version skill cases, leave `cases/skills/` empty.
The versioned skill folders remain the installed-SDK-specific source of truth.
