The answer should describe a dynamic storage pattern, not a single fixed table class for every interpolation policy.

Expected storage design:

- Base storage shape extends `PlatformTimeIndexMetaTable`.
- Index names are `["time_index", "asset_identifier"]`.
- `asset_identifier` references the canonical asset identity, typically `AssetTable.unique_identifier`.
- `__cadence__` should reflect the output cadence/upsample frequency.
- columns include `open_time`, `open`, `high`, `low`, `close`, `volume`, optional `trade_count`, optional `vwap`, and `interpolated`, each with labels and descriptions.
- a configured storage class should be derived from stable identity components:
  - source time-index MetaTable UID
  - source cadence
  - upsample frequency
  - interpolation rule
- these components belong in `__metatable_extra_hash_components__` and generated table identity, not as normal row columns unless they are actual row observations.

Expected DataNode design:

- config contains update-scoped and dependency-defining values, including source table UID or explicit source instance, upsample frequency, interpolation rule, and asset scope.
- config validation should require exactly one source path when supporting both source instance and source table UID.
- source `DataNode` or `APIDataNode` is resolved in constructor/setup and returned from `dependencies()`.
- `update()` reads only the needed source window using `UpdateStatistics` and asset dimension range maps.
- `update()` does not construct dependency graphs dynamically from inside the method.
- output frame is indexed by `["time_index", "asset_identifier"]`.
- time index is normalized to exact `datetime64[ns, UTC]`.
- duplicate `(time_index, asset_identifier)` rows are rejected.

The answer should explain that source storage must be registered/bound before the dynamic storage class can derive source UID/cadence. If cadence is missing, the DataNode should fail clearly and ask for the source storage to declare cadence.

The answer should route dynamic storage class inclusion to the migration provider. If the configured dynamic storage table is new, generate/apply the migration before running the node.

It should reject:

- accepting arbitrary `storage_table` override when storage identity must be derived from interpolation config.
- hiding source price creation inside `update()`.
- putting source UID/cadence/rule into row columns as storage identity metadata.
- using provider ticker instead of `asset_identifier`.
- relying on full-history reads every run.
- using `test_node=True`.
