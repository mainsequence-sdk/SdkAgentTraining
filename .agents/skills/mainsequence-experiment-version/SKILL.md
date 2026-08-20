---
name: mainsequence-experiment-version
description: Use when updating the MainSequence SDK experiment workspace to a new public repository tag or commit, resolving and auditing the immutable source snapshot, deciding whether a new authored suite version is required, and updating compatibility and split mappings without committing SDK copies or run outputs.
---

# MainSequence Experiment Version

## Purpose

Advance `experiments/mainsequence-sdk/` to a new public MainSequence SDK
revision while keeping the reusable `ms_agent_eval` library independent of the
evaluated SDK.

## Read First

Read:

- `README.md`, `docs/structure.md`, and `docs/conventions.md`;
- `experiments/mainsequence-sdk/workspace.yaml`;
- the current target document, snapshot lock, compatibility maps, co-located
  suite/split documents, and evaluator profile;
- the new revision's exact `agent_scaffold/AGENTS.md` and configured
  `agent_scaffold/skills/**/SKILL.md` files from an external snapshot.

## Invariants

- The target is a GitHub URL plus tag or commit, not an installed package.
- Resolve every tag to a full commit before planning a run.
- Store extracted source and checkouts only under `MS_AGENT_EVAL_DATA_ROOT`.
- Commit only compact configuration and hash-bearing snapshot locks.
- Never create top-level `sdk/`, `cases/`, `runs/`, `reports/`, or `spikes/`.
- Do not add `mainsequence` as an `ms-agent-eval` dependency.
- Reuse a suite unless behavior or evaluation criteria materially changed.

## Workflow

### 1. Inspect and preserve the worktree

Run `git status --short` and identify edits within the experiment workspace.
Never overwrite unrelated or user-authored changes.

### 2. Update and resolve the target

Change the target's authored tag/commit, then run:

```bash
uv run ms-agent-eval target resolve mainsequence-sdk \
  --workspace experiments/mainsequence-sdk/workspace.yaml
uv run ms-agent-eval target snapshot mainsequence-sdk \
  --workspace experiments/mainsequence-sdk/workspace.yaml \
  --data-root "$MS_AGENT_EVAL_DATA_ROOT"
```

Record the requested ref, resolved commit, target hash, extraction hash,
inventory hash, file hashes, and exact instruction paths in the compact lock.

### 3. Compare instruction inventories and behavior

Compare the old and new locks and external snapshot bytes. Classify units as
unchanged, added, removed, renamed/split, or behaviorally changed. Exact file
hash changes require review; they do not automatically require a new suite.

### 4. Decide suite reuse versus a new version

Create a new suite version only when unit boundaries, expected correct behavior,
evaluator criteria, or case validity changed materially. Do not version suites
for dependency-only or irrelevant source changes.

When creating a suite version:

- seed only compatible cases;
- update suite/unit/case metadata;
- mark migrated cases pending revalidation;
- assign leakage-resistant split groups;
- revalidate expected responses and rubrics against the new locked source.

### 5. Update compatibility and experiments

Create an exact snapshot/suite compatibility document. Every mapped unit and
case must exist in both the snapshot and suite. Keep `suite.yaml`, `split.json`,
and `units/` together under the suite version. Update plans to select the
intended snapshot, suite, evaluator, runtime, program, provider, storage, and
optional optimizer.

### 6. Validate

Run:

```bash
uv run ms-agent-eval config validate \
  --workspace experiments/mainsequence-sdk/workspace.yaml
uv run pytest tests/test_mainsequence_pack.py \
  tests/test_case_evaluator_metadata.py \
  tests/test_mainsequence_optimization_gate.py
```

Also verify the target is locked to the full commit, every configured source
path is exact, case counts and split assignments match, active evaluators are
calibrated, and no source clone or runtime artifact exists in the Git workspace.

## Final Response

Report the requested ref, resolved commit, snapshot id/hash, suite reused or
created, migration/revalidation state, compatibility/split changes, validation
results, and remaining evaluator or live-provider gates.
