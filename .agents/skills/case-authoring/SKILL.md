---
name: case-authoring
description: Use when creating, updating, reviewing, or planning evaluation cases in MS Agent Eval experiment workspaces, including case.yaml, prompts, expected responses, rubrics, case-bank metadata, and cases grounded in immutable repository snapshots or training-source documents.
---

# Case Authoring

## Purpose

Create reusable evaluation cases without committing evaluated-repository
snapshots or model-generated runtime data. An experiment workspace owns its
authored suites; the external data root owns resolved source and run artifacts.

## Read First

Before changing a case, read:

- `README.md`, `docs/structure.md`, and `docs/conventions.md`;
- the workspace target, snapshot lock, compatibility map, and suite manifest;
- the relevant immutable upstream instruction file identified by the snapshot
  lock;
- the target unit's `README.md` and `skill.yaml` in the suite;
- the relevant evaluator specification;
- any referenced source note under the workspace's `sources/`;
- the configured trusted evaluator under the workspace's `evaluators/`.

For the MainSequence workspace, start from:

```text
experiments/mainsequence-sdk/targets/mainsequence-sdk.yaml
experiments/mainsequence-sdk/snapshots/
experiments/mainsequence-sdk/compatibility/
experiments/mainsequence-sdk/suites/<version>/
```

Use `mainsequence-experiment-version` when changing the target revision,
snapshot lock, compatibility mapping, or suite version.

## Ownership Rules

- Put authored cases only under
  `experiments/<workspace>/suites/<version>/units/<unit>/cases/`.
- Co-locate `suite.yaml`, `split.json`, and `units/` under the suite version.
- Put compact target, snapshot, compatibility, evaluator, and profile documents
  in the experiment workspace.
- Put repository checkouts, extracted source, prompts sent to models, responses,
  evaluations, optimizer artifacts, and reports under `MS_AGENT_EVAL_DATA_ROOT`.
- Keep only minimal deterministic regression inputs under `tests/fixtures/`.
- Never create top-level `cases/`, `sdk/`, `runs/`, `reports/`, or `spikes/`.
- Never copy an upstream `SKILL.md` into an authored suite.

## Required Decisions

Before writing, determine:

1. Experiment workspace and target id.
2. Resolved source commit and snapshot lock.
3. Suite id/version and instruction unit id.
4. Immutable upstream instruction path.
5. Grounding source material.
6. Behavior being evaluated and why it is difficult.
7. Expected answer mode and artifacts.
8. Evaluator name, method, and status.
9. Hard-fail criteria and quality criteria.
10. Leakage-resistant split group.

Stop and ask a narrow question if local configuration and locked source cannot
resolve one of these decisions.

## Workflow

### 1. Resolve the exact source

Use the target configuration and snapshot lock. Tags are author input; the full
resolved commit is the evaluation identity. Read source from the immutable
external snapshot or the exact upstream commit, never from memory or an
installed package.

For supporting context, cite an immutable GitHub blob URL or the snapshot id plus
its exact `source_path`. Do not cite deleted local snapshot paths.

### 2. Design the evaluation first

Define the simulated user request, correct decisions, likely mistakes,
hard-fails, scored qualities, and required verification before editing files.
Prefer one focused case over a broad case spanning unrelated units.

### 3. Keep prompts self-contained without leaking the rubric

Prompts must include necessary task context but must not reveal reference
implementations, exact checklist items, required symbol names merely as hints,
or the expected answer. State whether the response should explain, plan, patch,
run commands, design artifacts, or combine those modes.

### 4. Use the standard case shape

```text
experiments/<workspace>/suites/<version>/units/<unit>/cases/<case-id>/
├── case.yaml
├── prompt.md
├── expected/
│   ├── response.md
│   └── artifacts/       optional
└── rubric.yaml
```

Do not add empty placeholder directories or files.

### 5. Write explicit metadata

`case.yaml` must identify the case, suite version, target revision basis, unit,
difficulty, requirements, success conditions, evaluator, and supporting source.
Implementation-derived cases must use repository URLs, versions/refs,
repository-relative files, and symbols—not local checkout paths.

Every evaluator block must declare an exact namespaced name, method, and one of:

- `active` with `rule-based-checklist`;
- `manual_review_required` with `human-review`;
- `not_evaluable` with `none`.

### 6. Write expected output and rubric

Describe semantic requirements, commands, artifacts, reasoning, and non-goals in
`expected/response.md`. Separate binary hard-fails from scored quality criteria
in `rubric.yaml`. Penalize invented APIs, stale target behavior, wrong routing,
missing verification, source leakage, and missing evaluator identity.

### 7. Preserve dataset governance

Assign related or paraphrased cases to one leakage-resistant group. Optimization
may use train/development only. Never use held-out test feedback to revise a
candidate prompt or compiled program.

## Validation

Before finishing:

- validate the entire workspace with `ms-agent-eval config validate`;
- load every changed `case.yaml` through `CaseDefinition`;
- verify required files and exact evaluator metadata;
- verify cited immutable source paths against the snapshot lock;
- verify prompts do not expose rubric answers or reference implementations;
- update suite/unit indexes when adding or removing cases;
- run evaluator calibration and the relevant tests;
- confirm no runtime output was written inside the Git workspace.

## Final Response

Report the workspace, target commit, suite version, unit, cases changed, source
material, evaluator status, validation performed, and remaining evaluator or
revalidation gaps.
