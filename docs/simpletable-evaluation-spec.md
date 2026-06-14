# SimpleTable Evaluation Spec

This document defines how to evaluate Main Sequence `SimpleTable` and `SimpleTableUpdater` construction cases against the installed SDK.

Current checked SDK basis: `mainsequence==3.17.38`

SDK `4.4.5` is now the active snapshot for `cases/v2`; this spec is carried forward and must be revalidated against the 4.x SDK code before it is treated as current for new SimpleTable construction cases.

Primary source-of-truth inputs:

- `agent_scaffold/skills/data_publishing/simple_tables/SKILL.md`
- `docs/knowledge/simple_tables/simple_table.md`
- `docs/knowledge/simple_tables/filtering.md`
- `docs/tutorial/working_with_simple_tables.md`
- `mainsequence/tdag/simple_tables/models.py`
- `mainsequence/tdag/simple_tables/schema.py`
- `mainsequence/tdag/simple_tables/filters.py`
- `mainsequence/tdag/simple_tables/table_nodes.py`
- `mainsequence/tdag/simple_tables/persist_managers.py`
- `mainsequence/tdag/pydantic_metadata.py`

## Evaluation Model

Score `SimpleTable` construction cases in two layers:

1. `hard_fail_checks`
2. `quality_checks`

If any hard-fail check fails, the case should fail regardless of quality score.

## Hard-Fail Checks

Use these as binary checks.

### 1. Schema contract

- The row model must subclass `SimpleTable`.
- The schema must not declare `id`.
- The schema must not rely on undeclared extra fields.
- Logical and physical column names must be `63` characters or fewer.

### 2. Field metadata contract

- `ForeignKey.target` must be a non-empty dependency key.
- `ForeignKey.on_delete` must be one of:
  - `cascade`
  - `restrict`
  - `set_null`
- A field must not declare multiple `ForeignKey` metadata entries.
- A field must not declare multiple `Index` metadata entries.
- A field must not declare multiple `Ops` metadata entries.

### 3. Updater construction contract

- The updater must subclass `SimpleTableUpdater`.
- `SIMPLE_TABLE_SCHEMA` must be defined.
- `SIMPLE_TABLE_SCHEMA` must be a `SimpleTable` subclass.
- The updater configuration must be a `SimpleTableUpdaterConfiguration` / `BaseConfiguration` subclass.
- Removed hashing patterns must not appear:
  - `_ARGS_IGNORE_IN_STORAGE_HASH`
  - `init_meta`
  - `ignore_from_storage_hash`

### 4. Hash classification contract

- Fields that should change table identity must not be marked `update_only`.
- Updater-scope fields should be marked `json_schema_extra={"update_only": True}`.
- Runtime-only descriptive fields should be marked `json_schema_extra={"runtime_only": True}`.
- No config field may be both `update_only` and `runtime_only`.

### 5. Foreign-key dependency contract

- Every `ForeignKey.target` must resolve through `dependencies()`.
- Every resolved foreign-key dependency must be a `SimpleTableUpdater`.
- A foreign key must not point to the updater itself.
- Cyclic simple-table foreign-key resolution is invalid.

### 6. `update()` return contract

- `update()` must not return `None`.
- `update()` must return either:
  - a sequence of `SIMPLE_TABLE_SCHEMA` instances
  - `(sequence_of_schema_instances, overwrite_bool)`
- Returned records must be instances of the declared schema.

### 7. Mutation contract

- Insert payloads may omit `id`.
- Overwrite/upsert payloads must include backend-managed `id` when mutation of existing rows is claimed.
- `delete()` requires either:
  - a row `id`
  - a record with populated `id`

### 8. Filter and join contract

- Typed backend filters must only use fields with `Ops.filter=True`.
- Ordering keys must only use fields with `Ops.order=True`.
- Simple-table requests must target a concrete `storage_hash`.
- Simple-table joins must target a concrete `storage_hash`.
- Simple-table joins must not use `node_unique_identifier`.
- `joins=` must contain only `JoinSpec` or `JoinHandle`.

## Quality Checks

These should be scored, not treated as immediate failure unless the case says otherwise.

Suggested default scale:

- `1.0` correct
- `0.5` partial
- `0.0` missing or wrong

### A. Table choice and scope

- The solution uses `SimpleTable` for row-oriented non-time-series data.
- The solution does not use `SimpleTable` where a `DataNode` table is the natural fit.
- The table scope stays within the intended lightweight project-table model rather than growing into a full ORM design.

### B. Schema design quality

- Business keys are intentional and readable.
- Fields that are filtered often are marked with `Ops(filter=True)` intentionally.
- Fields that are sorted often are marked with `Ops(order=True)` intentionally.
- Useful lookup fields use `Index(...)` intentionally.
- Field names are concise, stable, and backend-safe.

### C. Id and mutation workflow

- The solution clearly separates:
  - insert without ids
  - read rows back
  - mutate later by backend id
- It does not confuse a business key with the overwrite key.
- It explains when overwrite is safe and when insert-only is safer.

### D. Foreign-key workflow quality

- Parent-child relationships are modeled through dependency keys cleanly.
- Downstream updates resolve parent ids from returned rows.
- Foreign-key field names are explicit and readable.
- Delete semantics are intentional through `on_delete`.

### E. Updater design

- `dependencies()` is deterministic and easy to read.
- `update()` is narrow in purpose and returns typed records directly.
- Schema resolution is not hidden behind dynamic or fragile control flow.
- Config fields are classified correctly into dataset identity, updater scope, and runtime-only metadata.

### F. Filtering and join design

- Filters are built from the typed schema surface.
- `execute_filter()` is used through the updater, not bypassed with low-level request assembly unless the case explicitly requires it.
- Join filters use the declared schema and dependency relationships cleanly.
- Filter expressions match the fields actually declared as filterable/orderable.

### G. Operational clarity

- The proposed workflow explains how rows are inserted, queried, upserted, and deleted.
- The answer distinguishes verified SDK behavior from assumptions.
- The answer does not invent unsupported overwrite keys, join targets, or filter behavior.

## Recommended Standards

These are not mandatory SDK contracts, but they should be treated as strong positives during evaluation and case authoring.

### 1. Prefer `SimpleTable` only for the right shape

- Use `SimpleTable` for row-oriented operational or relational records inside a project.
- Prefer `DataNode` when the data is fundamentally a published time series keyed by `time_index` and `unique_identifier`.
- Avoid stretching `SimpleTable` into a full application ORM or broader database layer.

### 2. Keep schema and updater responsibilities clean

- Let `SimpleTable` define the row contract and field semantics.
- Let `SimpleTableUpdater` own writes, dependencies, hashing, and reads.
- Avoid hiding business logic in low-level persistence calls when `update()` can express it directly.

### 3. Design business keys intentionally

- Use readable stable business keys such as codes, names, or external ids when the table needs lookup semantics.
- Add `Index(unique=True)` when uniqueness is part of the domain contract.
- Keep the distinction clear between:
  - lookup key
  - uniqueness key
  - backend mutation key

### 4. Treat backend `id` as a runtime mutation handle

- Insert rows first without ids.
- Read rows back to recover backend-assigned ids.
- Use those ids for later sparse updates, upserts, and deletes.
- Explain this lifecycle explicitly in good answers.

### 5. Keep foreign-key flows explicit

- Name foreign-key fields clearly, usually with `_id` suffix semantics.
- Resolve parent ids from actual stored parent rows before building children.
- Keep parent-child sequencing visible in the updater workflow.
- Choose `on_delete` behavior intentionally rather than relying on defaults without explanation.

### 6. Mark query ergonomics intentionally

- Add `Ops(filter=True)` to fields that are part of real lookup or workflow patterns.
- Add `Ops(order=True)` only where ordering is genuinely useful.
- Add `Index(...)` to fields that are frequently filtered or carry uniqueness constraints.
- Avoid marking every field as operationally important without reason.

### 7. Keep updater logic deterministic

- `dependencies()` should return a stable and readable map.
- `update()` should build rows in a deterministic order when practical.
- Avoid dynamic dependency construction or hidden control-flow branches that make storage resolution hard to reason about.

### 8. Prefer typed filter workflows

- Build filters from `MyTable.filters.<field>...`.
- Execute them through `my_updater.execute_filter(...)`.
- Prefer join helpers that reflect the declared schema instead of inventing raw backend request payloads.

### 9. Write examples that match real mutation semantics

- Insert examples should omit `id` unless the row is already known to exist.
- Overwrite examples should show where the ids came from.
- Delete examples should operate on returned ids or records with ids.
- Good examples should not imply that a unique business field automatically acts like a primary key for mutation.

### 10. Keep field and table naming backend-safe

- Use short, readable field names.
- Avoid names that approach the `63` character limit unless absolutely necessary.
- Keep foreign-key-derived physical names in mind, since `<name>_id` must also remain valid.

### 11. Prefer explanations that separate SDK facts from design advice

- State what the SDK enforces.
- State what is only recommended.
- State when a design is a tradeoff rather than the only valid option.

### 12. Keep SimpleTable answers operationally complete

- A strong answer should explain not only schema declaration, but also:
  - how rows are created
  - how related rows are linked
  - how records are queried back
  - how later mutations happen safely

## Issue Classification

Use these labels during review and evaluator output:

- `hard_fail`
  Violates an enforced SDK contract or invalidates execution.
- `contract_break`
  Changes row identity, foreign-key meaning, or overwrite semantics unsafely.
- `major_quality_issue`
  Valid shape, but likely to cause operational or maintenance problems.
- `minor_quality_issue`
  Acceptable implementation, but below standard.

## Default Evaluator Output Shape

Recommended structure for SimpleTable-construction evaluations:

```json
{
  "case_id": "st-001-example",
  "sdk_version": "3.17.38",
  "method": "rule-based-checklist",
  "passed": false,
  "hard_fail_checks": [
    {
      "id": "schema-does-not-declare-id",
      "passed": true,
      "notes": "No user-authored id field was found."
    }
  ],
  "quality_checks": [
    {
      "id": "id-mutation-workflow",
      "score": 0.5,
      "notes": "Business key was explained clearly, but overwrite safety was underspecified."
    }
  ],
  "findings": [
    {
      "severity": "hard_fail",
      "message": "ForeignKey target 'customers' is not declared in dependencies()."
    }
  ]
}
```

## Important Clarifications

### `id` is runtime-available, not user-declared

The evaluator should treat these as simultaneously true:

- declaring `id` in a `SimpleTable` subclass is invalid
- filtering on `id` at runtime is valid
- later updates and deletes may rely on backend-returned `id`

### Overwrite is keyed by backend `id`

For `SimpleTableUpdater`, overwrite/upsert should be evaluated against backend-managed row ids.

Do not score a business key such as:

- `customer_code`
- `external_id`
- `symbol`

as if it were the write key for overwrite unless the workflow first resolves that key back to backend `id`.

### `Ops.filter` and `Ops.order` are enforced; `Ops.insert` and `Ops.update` are not yet a hard-eval target

The current SDK actively enforces:

- filterability through `Ops.filter`
- orderability through `Ops.order`

The `Ops.insert` and `Ops.update` fields exist in the schema metadata, but I do not see equivalent active client-side enforcement in the current SDK path.

Evaluation should therefore:

- treat misuse of `Ops.filter` / `Ops.order` as hard failures
- treat `Ops.insert` / `Ops.update` mostly as design metadata for now

## Recommended Next Step

Implement evaluator rules in this order:

1. schema/id hard fails
2. foreign-key/dependency hard fails
3. update return and overwrite hard fails
4. filter/join hard fails
5. schema/updater workflow quality checks
