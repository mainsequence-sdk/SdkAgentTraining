The response should use the storage-first SDK 4.x pattern.

It should define or describe a `PlatformTimeIndexMetaTable` storage class before the DataNode:

- project-prefixed `__tablename__`, preferably via `schema_table_name(...)`.
- `__metatable_namespace__` and `__metatable_identifier__`.
- intention-rich `__metatable_description__`.
- `__time_index_name__ = "time_index"`.
- `__cadence__ = "1d"`.
- `__index_names__ = ["time_index", "asset_identifier"]`.
- `time_index` as timezone-aware SQLAlchemy `DateTime`.
- `asset_identifier` as string FK to the asset table's canonical `unique_identifier`.
- columns for `risk_score`, `risk_bucket`, and `model_version`, each with `mapped_column(info={"label": ..., "description": ...})`.
- no manual duplicate of the full-grain unique index implied by `PlatformTimeIndexMetaTable`.
- optional additional lookup indexes only when they support real read patterns.

It should describe a `DataNodeConfiguration` with update-scoped fields only, such as vendor/source name, source location, model family, or asset scope if those change the update process. It should explicitly keep schema, index names, foreign keys, labels, and published metadata out of config. Config fields should use `Field(...)` with meaningful descriptions, and non-hash runtime fields should not be normal config fields unless using the supported `json_schema_extra={"hash_excluded": True}`.

The DataNode should:

- call `super().__init__(config=config, storage_table=RiskScoreStorage, hash_namespace=...)`.
- expose deterministic dependencies in `dependencies()`, or `{}` if there are none.
- use `UpdateStatistics` to fetch only new rows by default.
- return an empty `pd.DataFrame()` for no-op updates, not `None`.
- return a DataFrame indexed by `["time_index", "asset_identifier"]`.
- normalize the first index level to exact `datetime64[ns, UTC]`.
- reject or prevent duplicate `(time_index, asset_identifier)` rows.
- use `asset_identifier` as canonical identity and treat vendor ticker as payload/source metadata only if needed.

The response should say storage registration is migration-first: add the storage model to the selected MetaTable migration provider and run:

```bash
mainsequence migrations current --provider <package>.migrations:migration
mainsequence migrations revision --provider <package>.migrations:migration -m "add asset risk score storage"
mainsequence migrations upgrade --provider <package>.migrations:migration head
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

It should reject:

- putting schema or FK data in `DataNodeConfiguration`.
- using `test_node=True`.
- relying on DataNode construction to author/register the table.
- using vendor ticker as the storage identity dimension.
- returning naive or microsecond-resolution datetimes.
- raw SQL writes or deletes for normal DataNode persistence.
