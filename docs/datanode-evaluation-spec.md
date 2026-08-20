# DataNode Evaluation Spec

This document defines how to evaluate Main Sequence `DataNode` construction cases against the installed SDK.

Current checked SDK basis: `mainsequence==3.17.38`

SDK `4.4.5` is the configured source for `experiments/mainsequence-sdk/workspace.yaml`; use this document only as a coverage request for the DSPy case builder, which must ground new DataNode cases in the active immutable snapshot.

Primary source-of-truth inputs:

- `agent_scaffold/skills/data_publishing/data_nodes/SKILL.md`
- `docs/tutorial/creating_a_simple_data_node.md`
- `docs/tutorial/multi_index_columns_working_with_assets.md`
- `docs/knowledge/data_nodes.md`
- `mainsequence/tdag/data_nodes/data_nodes.py`
- `mainsequence/tdag/data_nodes/models.py`
- `mainsequence/tdag/data_nodes/run_operations.py`
- `mainsequence/tdag/pydantic_metadata.py`

## Evaluation Model

Score `DataNode` cases in two layers:

1. `hard_fail_checks`
2. `quality_checks`

If any hard-fail check fails, the case should fail regardless of quality score.

## Hard-Fail Checks

Use these as binary checks.

### 1. Constructor and config contract

- The node must subclass `DataNode`.
- The constructor must call `super().__init__(config=...)`.
- The `config` object must be a `BaseConfiguration` / `DataNodeConfiguration` subclass.
- The implementation must not use removed patterns:
  - `_ARGS_IGNORE_IN_STORAGE_HASH`
  - `init_meta`
  - `ignore_from_storage_hash`

### 2. Hash classification contract

- Fields that change dataset meaning must not be marked `update_only`.
- Fields that are updater-scope only must be marked `json_schema_extra={"update_only": True}`.
- Fields that are descriptive/runtime-only must be marked `json_schema_extra={"runtime_only": True}`.
- No field may be both `update_only` and `runtime_only`.

### 3. `update()` return contract

- On the default `DataNode` path, `update()` must return a `pd.DataFrame`.
- Returning `None` is a failure.
- Returning an empty `pd.DataFrame()` when there is no new data is valid.

### 4. DataFrame validation contract

- The first index level must be `datetime64[ns, UTC]`.
- For non-DuckDB storage, all output column names must be lowercase strings.
- Output column names must be `63` characters or fewer.
- Datetime payload columns are forbidden.
- The output must not rely on `inf` or `-inf` surviving persistence.

### 5. MultiIndex contract

For asset-indexed tables:

- the first index level must be `time_index`
- the second index level must be `unique_identifier`
- the implementation must treat `unique_identifier` as the current standard
- `asset_symbol` is not a valid evaluation target for new node construction

### 6. Duplicate-key contract

- The node must not emit duplicate index keys.
- For single-index tables, duplicate `time_index` rows are a failure.
- For MultiIndex tables, duplicate `(time_index, unique_identifier)` rows are a failure.

## Quality Checks

These should be scored, not treated as immediate failure unless the case says otherwise.

Suggested default scale:

- `1.0` correct
- `0.5` partial
- `0.0` missing or wrong

### A. Dataset contract design

- Identifier choice is intentional and collision-aware.
- Dataset meaning is separated from updater scope.
- Breaking contract changes are treated explicitly.
- Published metadata is stable and readable.

### B. Incremental update behavior

- `update()` uses `self.update_statistics`.
- The implementation is incremental by default.
- Full-history fetches are avoided unless explicitly justified.
- Backfill behavior is controlled rather than implicit.

### C. Dependency design

- Dependencies are instantiated in `__init__`.
- `dependencies()` returns a deterministic dependency map.
- Dependency keys are short and descriptive.
- Dependencies are not created dynamically inside `update()`.

### D. Metadata quality

- `node_metadata` or `get_table_metadata()` is provided for production-quality nodes.
- `records` or `get_column_metadata()` is provided.
- `RecordDefinition.column_name` and `dtype` match the actual output.
- Metadata descriptions are useful for search and discovery.

### E. Asset-index discipline

For asset-indexed nodes:

- `unique_identifier` maps to platform asset identity.
- `get_asset_list()` reflects the effective asset scope.
- Asset resolution or registration is handled idempotently when needed.
- Asset universe is not incorrectly used as dataset meaning.

### F. Testing and isolation

- First validation runs use `hash_namespace(...)` or `test_node=True`.
- Namespace is used only for isolation, not business meaning.
- Test runs are bounded through `offset_start` or controlled update statistics.

### G. DataFrame hygiene

- Dtypes are stable across runs.
- Column names are concise and readable.
- Index order is sorted ascending when practical.
- Mixed `object` dtypes are avoided when possible.

## Issue Classification

Use these labels during review and evaluator output:

- `hard_fail`
  Violates an enforced SDK contract or invalidates execution.
- `contract_break`
  Changes dataset meaning, schema, identifier, or index shape unsafely.
- `major_quality_issue`
  Poor DataNode design likely to cause operational problems.
- `minor_quality_issue`
  Valid node, but below standard.

## Default Evaluator Output Shape

Recommended structure for DataNode-construction evaluations:

```json
{
  "case_id": "dn-001-example",
  "sdk_version": "3.17.38",
  "judge": "workspace DSPy LLM judge",
  "passed": false,
  "hard_fail_checks": [
    {
      "id": "update-returns-dataframe",
      "passed": true,
      "notes": "Returned a DataFrame."
    }
  ],
  "quality_checks": [
    {
      "id": "incremental-update",
      "score": 0.5,
      "notes": "Used update_statistics but still fetched more history than needed."
    }
  ],
  "findings": [
    {
      "severity": "hard_fail",
      "message": "Column name 'VeryLongColumnName...' exceeds 63 characters."
    }
  ]
}
```

## Important Clarifications

### `unique_identifier` is the standard

For MultiIndex asset tables, the evaluator should treat `unique_identifier` as authoritative.

Do not score against `asset_symbol` naming from older internal code paths.

### `update()` should not return `None`

Although some older docs/comments imply `None` may mean "nothing new", the active default execution path raises if `update()` returns `None`.

Evaluation should therefore require:

- empty `pd.DataFrame()` for no-op updates
- not `None`

## Recommended Next Step

Implement evaluator rules in this order:

1. constructor/config hard fails
2. DataFrame hard fails
3. MultiIndex/asset hard fails
4. incremental/dependency quality checks
5. metadata quality checks
