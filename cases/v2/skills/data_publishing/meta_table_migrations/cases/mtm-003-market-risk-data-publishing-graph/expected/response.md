The answer should treat this as an integrated data-publishing graph:

- relational reference state uses platform-managed MetaTables.
- time-indexed facts use `PlatformTimeIndexMetaTable` storage owned by a DataNode.
- one SDK migration provider should include parent MetaTables and the DataNode storage class so FK/index DDL and catalog finalization are provider-scoped.

Expected MetaTables:

- `RiskModelTable`
  - UUID primary key.
  - unique `unique_identifier`.
  - fields such as display name, status, source, and metadata when useful.
  - lookup indexes for status/source if queried.
  - intention-rich table and column metadata.
- `RiskScenarioTable`
  - UUID primary key.
  - FK to `RiskModelTable.uid` or a clearly justified risk model identity target.
  - stable `scenario_key`.
  - composite unique index on `(risk_model_uid, scenario_key)`.
  - lookup indexes for model, scenario key, and status.
  - intentional `ondelete`, usually `CASCADE` only if scenarios are owned by a risk model, otherwise `RESTRICT`.

Expected DataNode storage:

- `RiskScoreStorage(PlatformTimeIndexMetaTable, Base)`.
- `__time_index_name__ = "time_index"`.
- `__cadence__ = "1d"` or another justified cadence.
- `__index_names__ = ["time_index", "asset_identifier", "risk_model_identifier", "scenario_key"]`.
- FK from `asset_identifier` to `AssetTable.unique_identifier`.
- FK from `risk_model_identifier` to `RiskModelTable.unique_identifier`, or a clearly justified alternative.
- composite FK from `(risk_model_identifier, scenario_key)` to the scenario business key if the SQLAlchemy design supports it, or an explanation that scenario rows should expose a stable scenario identifier used by storage.
- columns for risk score, bucket, exposure value, and model version with full column `info`.
- no manual duplicate of the full-grain unique index implied by `PlatformTimeIndexMetaTable`.
- optional lookup indexes only for additional read paths.

Expected DataNode boundary:

- `RiskScoresConfig(DataNodeConfiguration)` carries update-scoped fields such as source name, source location, model scope, scenario scope, or asset scope.
- schema, FK targets, index names, cadence, table descriptions, and column metadata stay on storage, not config.
- constructor calls `super().__init__(config=config, storage_table=RiskScoreStorage, hash_namespace=...)`.
- dependencies are deterministic and returned by `dependencies()`.
- `update()` uses `UpdateStatistics`, returns `pd.DataFrame()` for no-op, normalizes first index level to exact `datetime64[ns, UTC]`, and rejects duplicate full-grain index rows.

Expected migration provider:

- use `build_alembic_version_metatable(...)`.
- use `build_metatable_model_registry(...)` or explicit de-duplicated registry.
- use `build_metatable_migration_provider(...)`.
- include `RiskModelTable`, `RiskScenarioTable`, and `RiskScoreStorage` in `metatable_models`.
- use one provider unless the user defines independent lifecycle boundaries.

Expected commands:

```bash
mainsequence migrations current --provider risk_app.migrations:migration
mainsequence migrations revision --provider risk_app.migrations:migration -m "add market risk publishing graph"
mainsequence migrations upgrade --provider risk_app.migrations:migration head
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

Expected verification:

- provider imports.
- generated revision contains parent tables, child tables, storage table, FKs, and indexes.
- upgrade succeeds.
- provider-scoped MetaTable catalog rows finalize.
- runtime startup attaches registered MetaTables and TimeIndexMetaTables only.
- DataNode run is validated with an explicit `hash_namespace` in shared backends.

The answer should reject:

- putting all reference and time-indexed facts into one MetaTable.
- putting schema or FK metadata in DataNode config.
- calling model `.register()` in runtime startup.
- using raw SQL DDL or direct backend payloads.
- relying on provider ticker instead of canonical asset identity.
- creating dependency graphs dynamically in `update()`.
- using raw SQL deletes for DataNode storage cleanup.
