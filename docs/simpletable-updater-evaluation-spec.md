# SimpleTableUpdater Evaluation Spec

This document defines how to evaluate Main Sequence `SimpleTableUpdater` construction cases against the installed SDK.

Current checked SDK basis: `mainsequence==3.17.38`

SDK `4.4.5` is now the active snapshot for `experiments/mainsequence-sdk/suites/v2`; this spec is carried forward and must be revalidated against the 4.x SDK code before it is treated as current for new SimpleTableUpdater construction cases.

Primary source-of-truth inputs:

- `agent_scaffold/skills/data_publishing/simple_tables/SKILL.md`
- `docs/knowledge/simple_tables/simple_table.md`
- `docs/knowledge/simple_tables/filtering.md`
- `docs/tutorial/working_with_simple_tables.md`
- `mainsequence/tdag/simple_tables/table_nodes.py`
- `mainsequence/tdag/simple_tables/persist_managers.py`
- `mainsequence/tdag/simple_tables/models.py`
- `mainsequence/tdag/simple_tables/schema.py`
- `mainsequence/tdag/simple_tables/filters.py`
- `mainsequence/tdag/pydantic_metadata.py`

## Scope

Use this spec when the case is evaluating updater behavior rather than only schema design.

This includes:

- `SIMPLE_TABLE_SCHEMA` ownership
- updater configuration and hashing
- `dependencies()` design
- foreign-key target resolution
- `update()` return behavior
- insert versus overwrite behavior
- filtering through the updater
- id-aware mutation workflows

This spec is intentionally different from the base SimpleTable spec:

- the `SimpleTable` spec focuses on row schema correctness
- this spec focuses on table ownership, mutation semantics, and runtime workflow

## Evaluation Model

Score `SimpleTableUpdater` cases in two layers:

1. `hard_fail_checks`
2. `quality_checks`

If any hard-fail check fails, the case should fail regardless of quality score.

## Hard-Fail Checks

Use these as binary checks.

### 1. Updater type and schema ownership

- The implementation must subclass `SimpleTableUpdater`.
- `SIMPLE_TABLE_SCHEMA` must be defined.
- `SIMPLE_TABLE_SCHEMA` must be a `SimpleTable` subclass.
- The updater must not blur ownership by treating the schema as optional or dynamically ambiguous.

### 2. Configuration and hash contract

- The updater must be constructed with a `SimpleTableUpdaterConfiguration` / `BaseConfiguration` subclass.
- Removed hashing patterns must not appear:
  - `_ARGS_IGNORE_IN_STORAGE_HASH`
  - `init_meta`
  - `ignore_from_storage_hash`
- Config fields must respect current metadata rules:
  - `json_schema_extra={"update_only": True}`
  - `json_schema_extra={"runtime_only": True}`
- No config field may be both `update_only` and `runtime_only`.

### 3. Foreign-key dependency resolution contract

- Every `ForeignKey.target` in the schema must resolve through `dependencies()`.
- Resolved foreign-key dependencies must be `SimpleTableUpdater` instances.
- A foreign key must not point to the updater itself.
- Cyclic simple-table foreign-key resolution is invalid.

### 4. `update()` return contract

- `update()` must not return `None`.
- `update()` must return either:
  - a sequence of `SIMPLE_TABLE_SCHEMA` instances
  - `(sequence_of_schema_instances, overwrite_bool)`
- Returned items must be instances of the declared schema.
- Returning strings, dicts, DataFrames, or mixed record types is invalid on the default updater path.

### 5. Mutation semantics contract

- Insert-only behavior is valid when rows do not yet have backend ids.
- If overwrite/upsert is claimed, returned rows must already include backend-managed ids.
- The updater must not imply that a business key alone is the overwrite key.
- `delete()` requires:
  - a row id
  - or a record with populated `id`

### 6. Filter execution contract

- The user-facing query path must run through `execute_filter()`.
- The updater must resolve the real backend table through `storage_hash`.
- Typed filters must only use fields allowed by `Ops.filter=True`.
- Ordering keys must only use fields allowed by `Ops.order=True`.
- Join requests must use valid simple-table join semantics:
  - concrete `storage_hash`
  - no `node_unique_identifier`
  - `joins=` contains only `JoinSpec` or `JoinHandle`

### 7. Response validation contract

- Rows read through the updater must validate back into the declared `SimpleTable` model.
- The workflow must not rely on malformed response payload shape.

## Quality Checks

These should be scored, not treated as immediate failure unless the case says otherwise.

Suggested default scale:

- `1.0` correct
- `0.5` partial
- `0.0` missing or wrong

### A. Updater responsibility clarity

- The updater clearly owns backend table lifecycle, not just row construction.
- The answer distinguishes schema declaration from updater workflow.
- The updater design is cohesive rather than mixing persistence, schema, and unrelated orchestration concerns.

### B. Dependency design

- `dependencies()` is deterministic and easy to read.
- Dependency keys are stable and descriptive.
- Parent updaters are instantiated cleanly.
- The solution does not construct dependencies ad hoc inside `update()`.

### C. Foreign-key workflow quality

- Parent rows are read back to recover backend ids before children are built.
- The workflow clearly explains how parent ids become child foreign keys.
- `on_delete` behavior is intentional.
- The relationship path is understandable from the updater code and explanation.

### D. Insert versus overwrite judgment

- The solution chooses insert-only when ids do not exist yet.
- The solution chooses overwrite/upsert only when it already has backend ids.
- The explanation makes the overwrite key explicit.
- The updater does not overuse overwrite where insert-only would be safer.

### E. Id lifecycle clarity

- The answer explains the lifecycle:
  - insert
  - read back ids
  - later mutate by id
- Sparse mutation examples show where ids came from.
- Delete examples use returned ids correctly.

### F. Filter and join workflow quality

- Filters are built from the typed schema surface.
- Queries are executed through the updater.
- Join filters reflect actual declared relationships cleanly.
- The answer does not bypass the typed system without good reason.

### G. Configuration quality

- Config fields are classified correctly into:
  - table identity
  - updater-only scope
  - runtime-only descriptive metadata
- Configuration remains small and intentional.
- Hash-sensitive fields are not mixed with runtime-only descriptive knobs.

### H. Operational completeness

- The updater workflow explains how records enter the table.
- The updater workflow explains how records are queried back.
- The updater workflow explains how later mutations happen safely.
- The proposed flow could realistically be maintained by another engineer.

## Recommended Standards

These are not mandatory SDK contracts, but they should be treated as strong positives during evaluation.

### 1. Keep updater logic narrow

- `update()` should build the next intended records directly.
- Avoid turning `update()` into a broad orchestration function.
- Keep foreign-key resolution and id-recovery readable.

### 2. Prefer explicit parent-child sequencing

- Insert parent rows first when they do not exist.
- Read back parent ids explicitly.
- Build child rows from those resolved ids.
- Avoid hidden assumptions that parent ids already exist.

### 3. Make overwrite semantics explicit

- Good answers should say whether the updater is:
  - insert-only
  - id-aware overwrite
  - mixed workflow
- Good examples should show why overwrite is safe.

### 4. Keep examples faithful to SDK semantics

- Insert examples should not send placeholder ids.
- Upsert examples should not pretend business keys act as backend row ids.
- Filter examples should use `execute_filter(...)`.
- Delete examples should operate on real ids.

### 5. Prefer deterministic read-modify-write patterns

- Read existing rows once when needed.
- Build an explicit mapping such as `business_key -> id`.
- Reuse that mapping for downstream mutation.
- Avoid repeated ambiguous queries that make overwrite logic fragile.

### 6. Keep dependency naming clear

- Use dependency keys that describe the role of the parent table.
- Avoid vague names that make `ForeignKey("...")` hard to interpret.

### 7. Separate SDK facts from design advice

- Strong answers say what the SDK enforces.
- Strong answers say what is just the safer pattern.
- Strong answers avoid presenting recommendations as if they were hard runtime rules.

## Issue Classification

Use these labels during review and evaluator output:

- `hard_fail`
  Violates an enforced updater/runtime contract.
- `contract_break`
  Misstates overwrite semantics, foreign-key meaning, or updater ownership.
- `major_quality_issue`
  Valid updater shape, but likely to create maintenance or mutation problems.
- `minor_quality_issue`
  Acceptable implementation, but below standard.

## Default Evaluator Output Shape

Recommended structure for SimpleTableUpdater-construction evaluations:

```json
{
  "case_id": "stu-001-example",
  "sdk_version": "3.17.38",
  "method": "rule-based-checklist",
  "passed": false,
  "hard_fail_checks": [
    {
      "id": "simple-table-schema-defined",
      "passed": true,
      "notes": "SIMPLE_TABLE_SCHEMA points to a SimpleTable subclass."
    }
  ],
  "quality_checks": [
    {
      "id": "insert-vs-overwrite-judgment",
      "score": 0.5,
      "notes": "Correctly preferred insert-only, but did not explain the id recovery path."
    }
  ],
  "findings": [
    {
      "severity": "hard_fail",
      "message": "Overwrite was proposed without backend-managed ids on returned rows."
    }
  ]
}
```

## Important Clarifications

### `SimpleTableUpdater.update()` does not return dicts on the default path

Even though helper methods like `insert_records()` and `upsert_records()` will validate dict payloads, the default `update()` contract is stricter:

- it expects schema instances
- not raw dict payloads

Evaluation should score raw-dict `update()` returns as invalid.

### Overwrite is not keyed by business fields

Do not treat fields such as:

- `customer_code`
- `external_id`
- `symbol`

as overwrite keys unless the updater explicitly reads rows back and resolves those values to backend `id`.

### Filtering is schema-first but updater-executed

The intended workflow is:

1. build the filter from the `SimpleTable` schema surface
2. execute it through `SimpleTableUpdater.execute_filter(...)`

The evaluator should reward answers that preserve both halves of that contract.

## Recommended Next Step

Implement evaluator rules in this order:

1. updater ownership hard fails
2. foreign-key/dependency hard fails
3. update return and overwrite hard fails
4. filter/join hard fails
5. workflow quality checks
