---
name: case-authoring
description: Use this skill when creating, updating, reviewing, or planning evaluation cases in the SdkAgentTraining repository, including writing case.yaml, prompt.md, expected responses, rubrics, skill case-bank READMEs, and cases derived from SDK skill snapshots or training-source documents.
---

# Case Authoring

## Purpose

Create reusable evaluation cases for this repository without mixing authored
case material, copied SDK skill snapshots, and model run outputs.

Use this skill for case work only. Use `new_version_creation` when the task is
about refreshing an installed SDK snapshot, deciding whether a new case-set
version is needed, or changing `sdk/<version>/case-map.yaml`.

## Read First

Before authoring or changing cases, read:

- `README.md`
- `docs/structure.md`
- `docs/conventions.md`
- the relevant evaluator spec under `docs/`
- the relevant training-source plan under `docs/training_sources/`, if any
- `sdk/<target-sdk-version>/case-map.yaml`
- `sdk/<target-sdk-version>/source-of-truth.yaml`
- `sdk/<target-sdk-version>/skills/<skill-path>/source/SKILL.md`
- the target case-bank `README.md` and `skill.yaml` under
  `cases/<case-set-version>/skills/<skill-path>/`

For reference-project-derived MetaTable/DataNode cases, also read:

- the relevant plan under `docs/training_sources/`
- the SDK `data_publishing/meta_tables`, `data_publishing/data_nodes`, and
  `data_publishing/meta_table_migrations` skill snapshots as relevant

## Ownership Rules

- Put authored cases only under `cases/<case-set-version>/skills/<skill-path>/cases/`.
- Put copied SDK skill source only under
  `sdk/<sdk-version>/skills/<skill-path>/source/SKILL.md`.
- Put model outputs only under `runs/sdk/<sdk-version>/...`.
- Do not copy `SKILL.md` into a case folder.
- Do not edit SDK snapshots while authoring cases unless the user explicitly
  asks for a local patched snapshot.
- Do not create a new case-set version unless SDK compatibility requires it;
  use the new-version skill for that decision.

## Required Decisions

Before creating files, decide and state:

1. Target SDK version.
2. Target case-set version.
3. Target skill path.
4. SDK source-of-truth file and upstream git ref being evaluated.
5. Source material used to ground the case.
6. Skill behavior being evaluated.
7. Difficulty level and why the task is difficult.
8. Expected answer mode: explanation only, code plan, code patch, CLI workflow,
   artifact design, or mixed.
9. Whether the case expects files, commands, or only a written answer.
10. Evaluator method and evaluator name.
11. Hard-fail criteria versus quality criteria.

If any decision cannot be made from local docs and files, stop and ask a narrow
question instead of inventing case semantics.

## Case Design Workflow

### 1. Confirm The Target Skill

Resolve the SDK skill source through the SDK snapshot and case map.

Check:

```text
sdk/<sdk-version>/case-map.yaml
sdk/<sdk-version>/source-of-truth.yaml
sdk/<sdk-version>/skills/<skill-path>/source/SKILL.md
cases/<case-set-version>/skills/<skill-path>/
```

The case must evaluate the skill text for that SDK version, not memory of older
SDK behavior.

For reference-project-derived cases, `case_source_of_truth` must cite the git
repository, package name, package version, and repository tag/ref for the
implementation being evaluated, plus repository-relative source files and
symbols. Do not store local checkout paths as the case source of truth. SDK
skill snapshots and planning docs belong under `supporting_context`, not under
the case source of truth. The upstream SDK audit anchor belongs in
`sdk/<sdk-version>/source-of-truth.yaml`.

### 2. Design The Evaluation Before Writing

Write down the intended target behavior before creating the case files.

The design must include:

- the precise user request simulated by the prompt
- the important concepts the model must apply
- what makes the task non-trivial
- expected correct decisions
- common wrong decisions to catch
- hard-fail checks
- quality checks
- expected verification or evidence

For complex domains, prefer one focused case over a broad case that evaluates
too many unrelated skills.

### 3. Keep Prompts Self-Contained But Not Overfed

The prompt should include enough task context for a model to act, but it should
not include the rubric answer. The prompt is the simulated user request, not
the evaluation checklist.

Good prompts:

- present realistic user intent
- include necessary local paths, names, and constraints
- force decisions that the skill should own
- avoid telling the model exactly which checklist items to recite
- specify whether code should be written or only planned
- hide the reference implementation package, repository, tag, and source files

Bad prompts:

- ask vague questions with no success condition
- copy the full expected answer into the task
- combine unrelated skills without clear routing criteria
- depend on hidden state that the runner cannot provide
- reveal the reference implementation package, repository, or source-of-truth
  used to derive the case
- include `Your answer should` checklists that mirror the rubric or skill rules
- tell the model to answer as a named skill owner when the runner already
  injects the target skill
- list SDK class names, method names, validation rules, or required decisions
  merely to cue the expected answer
- turn rubric bullets into prompt bullets
- use "include X, Y, and Z" framing when X, Y, and Z are exactly what the
  evaluator is supposed to discover from the injected skill

### 4. Use The Standard Case Folder Shape

Each case folder must use:

```text
cases/<case-set-version>/skills/<skill-path>/cases/<case-id>/
├── case.yaml
├── prompt.md
├── expected/
│   ├── response.md
│   └── artifacts/
└── rubric.yaml
```

Only include `expected/artifacts/` when artifacts are part of the expected
output. Keep empty placeholder files out unless the surrounding case bank
already uses them.

### 5. Write Case Metadata

`case.yaml` should include:

- `id`
- `title`
- `skill_path`
- `case_set_version`
- `authored_against_sdk_version`
- `tags`
- `difficulty`
- `requires`
- `success`
- `evaluator`
- `case_source_of_truth` for cases derived from an implementation
- `supporting_context` for SDK skills, planning docs, and evaluator specs

Recommended evaluator shape:

```yaml
evaluator:
  name: rule-based-checklist
  method: rule-based-checklist
```

If a human or model evaluator is intended, include its name explicitly.

### 6. Write Expected Output

`expected/response.md` should describe the expected answer at the right level of
specificity.

Use:

- required decisions
- required commands or file paths
- required reasoning
- required artifacts
- explicit non-goals

Do not make the expected response depend on exact prose unless the case is
testing wording. Prefer semantic requirements that a rubric can evaluate.

### 7. Write The Rubric

`rubric.yaml` must separate hard-fail checks from quality checks.

Hard-fail checks are binary and should fail the case regardless of quality
score. Quality checks can be scored.

Rubrics should penalize:

- wrong skill routing
- outdated SDK behavior
- invented commands or APIs
- missing verification
- mixing `cases/`, `sdk/`, and `runs/` responsibilities
- missing evaluator identity
- missing source grounding

For construction cases, also penalize implementation shortcuts that violate the
relevant evaluator spec.

## Reference-Derived Data-Publishing Case Rules

For reference-derived MetaTable and DataNode cases, evaluate architectural
discipline, not just syntax. These are evaluator targets. Keep them in
`expected/response.md` and `rubric.yaml`; do not paste them into `prompt.md`
as checklist hints.

MetaTable cases must test:

- row grain
- primary keys and business keys
- SQLAlchemy foreign keys and correct FK targets
- unique and lookup indexes
- `RESTRICT` versus `CASCADE`
- column labels and descriptions
- migration-provider inclusion
- no runtime `.register()`

DataNode cases must test:

- storage-first `PlatformTimeIndexMetaTable`
- config contains update-scoped fields only
- canonical identity dimensions such as `asset_identifier`,
  `portfolio_identifier`, `curve_identifier`, or `index_identifier`
- storage-table foreign keys
- `datetime64[ns, UTC]` output
- no duplicate index rows
- deterministic dependencies
- `UpdateStatistics` use for incremental behavior

Migration cases must test:

- SDK helper-based migration provider
- explicit model registry
- de-duplicated model graph
- correct `mainsequence migrations ... --provider ...` commands
- runtime attach-only behavior

## Validation Checklist

Before finishing case work, verify:

- the case folder is under the mapped case-set version
- `case.yaml`, `prompt.md`, `expected/response.md`, and `rubric.yaml` exist
- `skill_path` matches the SDK skill path exactly
- `authored_against_sdk_version` matches the SDK snapshot used
- `sdk/<target-sdk-version>/source-of-truth.yaml` exists and names the upstream
  git ref, or explicitly marks it unverified
- implementation-derived cases use `case_source_of_truth` with a git repository,
  package version, repository tag/ref, repository-relative source files, and
  symbols; they do not list docs or local checkout paths as the truth source
- prompts do not reveal the reference implementation package/repository and do
  not include checklist-style rubric hints
- the prompt is self-contained
- the expected response is not just a copy of the rubric
- the rubric has hard-fail and quality sections
- evaluator name and method are explicit
- README or skill metadata for the case bank is updated when a new case family
  is added

## Final Response Requirements

When reporting case-authoring work, include:

- case-set version
- SDK version
- skill path
- cases created or updated
- source-of-truth files or training sources used
- SDK source-of-truth git ref and verification status
- validation performed
- any remaining revalidation or evaluator gaps
