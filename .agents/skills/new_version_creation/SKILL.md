---
name: sdk-agent-training-new-version-creation
description: Use this skill when updating SdkAgentTraining for a new public mainsequence SDK version, deciding whether a new authored case-set version is required, refreshing sdk/<version>/ snapshots, creating cases/vN, and mapping the SDK to the correct case set.
---

# SDK Agent Training New Version Creation

## Purpose

Use this skill when the public `mainsequence` library changes and the training repo must decide how to represent that change.

The goal is to keep three things separate:

- installed SDK snapshots under `sdk/<sdk-version>/`
- authored case sets under `cases/<case-set-version>/`
- actual model outputs under `runs/sdk/<sdk-version>/...`

Do not mix authored cases into SDK snapshots.

## Source Of Truth

Before changing structure, read:

- `README.md`
- `docs/structure.md`
- `docs/conventions.md`
- `docs/sdk-cli-notes.md`
- the current `sdk/<latest-known-version>/case-map.yaml`
- the current `sdk/<latest-known-version>/source-of-truth.yaml`
- the current `cases/<latest-case-set-version>/manifest.yaml`

The local structure docs define how this repo should evolve.

## Required Decisions

Before creating anything, decide:

1. What SDK version is currently installed?
2. Does `sdk/<installed-version>/` already exist?
3. What public git repository, tag/ref, and commit is the installed SDK snapshot
   supposed to match?
4. Did the SDK skill bundle change materially?
5. Can the current case set still evaluate the new SDK?
6. Is a new case-set version required?
7. Which old case set should seed the new one, if any?

Do not create `cases/vN` just because a patch version changed.

## When To Create A New Case Set

Create a new `cases/vN` when at least one is true:

- the SDK changed major version
- the skill list changed materially
- skill boundaries moved or were renamed
- expected correct answers changed
- evaluator criteria changed
- old cases would be misleading if treated as current

Do not create a new case set when:

- only dependency versions changed
- the SDK snapshot changed but the skill behavior and evaluation criteria are still compatible
- the current case set can be reused by updating only `sdk/<version>/case-map.yaml`

## Standard Workflow

### 1. Inspect Current State

Run:

```bash
git status --short
uv run python -c 'import importlib.metadata as m; print(m.version("mainsequence"))'
find sdk -maxdepth 2 -type f \( -name manifest.json -o -name case-map.yaml \) | sort
find cases -maxdepth 2 -type d | sort
```

If there are unrelated dirty files, do not revert them.

If a dirty file is in a path you need to regenerate, stop and decide whether to preserve, migrate, or intentionally overwrite it.

### 2. Update The Installed SDK

For latest public SDK:

```bash
uv lock --upgrade-package mainsequence
uv add 'mainsequence==<resolved-version>'
```

Use an exact pin once the version is known. The training repo should be reproducible.

### 3. Refresh The SDK Snapshot

Run:

```bash
uv run python scripts/populate_training_skills.py
```

The script must:

- take no arguments
- read the installed `mainsequence` version
- import the installed `agent_scaffold` bundle
- copy `AGENTS.md` and each `SKILL.md` into `sdk/<installed-version>/`
- create or refresh `sdk/<installed-version>/manifest.json`
- create or preserve `sdk/<installed-version>/source-of-truth.yaml`
- create or refresh `sdk/<installed-version>/case-map.yaml`

The copied `SKILL.md` files must remain exact snapshots of the installed package.

`source-of-truth.yaml` must record the public git repository and tag/ref. If the
commit has been verified, record the resolved commit SHA and verification
method. If it has not been verified, keep `verification_status: unverified` and
do not claim that the snapshot is audit-complete.

### 4. Compare Skill Bundles

Compare old and new snapshots:

```bash
find sdk/<old-version>/skills -path '*/source/SKILL.md' | sed 's#^sdk/<old-version>/skills/##; s#/source/SKILL.md$##' | sort
find sdk/<new-version>/skills -path '*/source/SKILL.md' | sed 's#^sdk/<new-version>/skills/##; s#/source/SKILL.md$##' | sort
```

Classify changes:

- unchanged skill path
- added skill path
- removed skill path
- renamed or split skill
- behaviorally changed skill text

This classification drives the case-set decision.

### 5. Create A New Case Set When Needed

If a new case set is required:

- choose the next version, for example `v2`, `v3`
- create `cases/<new-case-set>/manifest.yaml`
- create `cases/<new-case-set>/skills/<skill-path>/` for every skill in the new SDK snapshot
- migrate cases only for skill paths that still exist and are plausibly compatible
- create empty `cases/` folders for new skill paths

Migrated cases must be marked:

```yaml
case_set_version: vN
target_sdk_version: <new-sdk-version>
migrated_from_case_set: vN-1
migration_status: pending_revalidation
```

Do not mark migrated cases as current until they have been reviewed against the new SDK skill text and current docs.

### 6. Update The New SDK Case Map

For a new case set, `sdk/<new-version>/case-map.yaml` should usually map every new SDK skill to the new case set:

```yaml
sdk_version: <new-sdk-version>
default_case_set: vN
skills:
  platform_operations/orchestration_and_releases:
    case_set: vN
```

Use a mixed map only when a specific skill can safely keep using an older case set.

### 7. Update Docs

When a new SDK version or case set is created, update:

- `README.md`
- `docs/structure.md`
- `docs/conventions.md`
- `docs/ollama-workflow.md` if examples mention a concrete SDK version
- any evaluator spec whose SDK basis is no longer current

If a spec has not been revalidated, say that directly:

```text
Current checked SDK basis: mainsequence==<old-version>
SDK <new-version> is the active snapshot for cases/<new-case-set>; this spec is carried forward and must be revalidated.
```

## Revalidation Rules

For each migrated case:

- read the target SDK `SKILL.md`
- read the case prompt, expected response, and rubric
- verify commands, APIs, filenames, and expected reasoning against the new SDK docs/source
- update the case if behavior changed
- mark the case as revalidated only after the expected answer and rubric are current

Recommended metadata after revalidation:

```yaml
migration_status: revalidated
validated_against_sdk_version: <new-sdk-version>
validated_by: <agent-or-human-name>
validated_at: <ISO-8601 timestamp>
```

## Validation Checklist

Before finishing, verify:

- `uv run python -c 'import importlib.metadata as m; print(m.version("mainsequence"))'` prints the intended version
- `sdk/<new-version>/manifest.json` exists
- `sdk/<new-version>/source-of-truth.yaml` exists and includes the upstream git
  repository and ref
- `sdk/<new-version>/case-map.yaml` exists
- the skill count in `manifest.json` matches copied `source/SKILL.md` files
- `cases/<new-case-set>/manifest.yaml` exists if a new case set was created
- every skill in `sdk/<new-version>/case-map.yaml` points to an existing case-set folder
- script compilation passes
- at least one known case resolves through the runner

Suggested checks:

```bash
python3 -m py_compile scripts/populate_training_skills.py scripts/run_ollama_case.py scripts/evaluate_case.py
uv run python -c 'from pathlib import Path; import scripts.run_ollama_case as r; v=r.read_sdk_version(); s=r.locate_sdk_root(v); p=r.resolve_case("or-001-recurring-artifact-job", s); print(v); print(p.relative_to(Path.cwd()))'
```

If the known case does not exist in the new case set, use another migrated case id.

## Things Not To Do

- Do not place authored cases under `sdk/<sdk-version>/`.
- Do not delete older SDK snapshots just because a new snapshot exists.
- Do not silently treat migrated cases as validated.
- Do not overwrite dirty skill edits without first identifying whether they are user-authored changes.
- Do not use the SDK snapshot as the place to patch upstream skill content unless the user explicitly asks for a local patched snapshot.

## Final Response Requirements

When reporting the result, include:

- installed SDK version
- new SDK snapshot path
- case-set version used
- whether cases were migrated or newly authored
- migration/revalidation status
- source-of-truth git ref and whether the commit was verified
- validation commands that passed
- any dirty or unresolved files left in the worktree
