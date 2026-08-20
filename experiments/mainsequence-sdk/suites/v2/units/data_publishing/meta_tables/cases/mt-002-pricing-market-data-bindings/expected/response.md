The response should separate two concerns:

- Pricing source-selection rows are MetaTables.
- Discount curve and index fixing observations are DataNode outputs backed by `PlatformTimeIndexMetaTable` storage.

The expected design should include:

- `PricingMarketDataSetTable`: one row per named source set, keyed by a stable `set_key` such as `default`, `eod`, `live`, or `risk_manager`.
- `PricingMarketDataSetBindingTable`: one row per `(market_data_set_uid, concept_key)` binding, pointing to the backend DataNode storage table UID for that concept.

The response should require:

- `PlatformManagedMetaTable` model classes with project-prefixed physical names.
- `__metatable_identifier__`, intention-rich `__metatable_description__`, and column `info` metadata.
- UUID primary keys for both tables.
- unique index on `PricingMarketDataSetTable.set_key`.
- composite unique index on `(market_data_set_uid, concept_key)`.
- FK from binding table to market-data set table, with `ondelete="CASCADE"` justified because bindings are dependent rows owned by the set.
- lookup indexes for `concept_key`, `data_node_uid`, and operational fields such as status or source when present.
- `data_node_uid` as a backend DataNode storage table UID used by `APIDataNode.build_from_table_uid(...)`.
- optional diagnostic storage identifier only as metadata, not as the authoritative runtime pointer.

The response should describe governed operations such as:

- upsert market-data set by `set_key`.
- upsert binding by `(market_data_set_uid, concept_key)`.
- resolve a binding's `data_node_uid` by `(set_key, concept_key)`.
- list bindings for a set.

It should state that compiled SQL operations must declare the MetaTable UID scope and read/write access for every table touched, and must not execute unrestricted SQL outside the MetaTable operation contract.

The response should route schema lifecycle through the selected migration provider and commands:

```bash
mainsequence migrations current --provider <package>.migrations:migration
mainsequence migrations revision --provider <package>.migrations:migration -m "add pricing market data bindings"
mainsequence migrations upgrade --provider <package>.migrations:migration head
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

It should reject:

- storing curve observations or fixing observations in these source-selection MetaTables.
- using static storage identifier constants as authoritative pointers.
- resolving source data by hardcoded physical table names.
- putting asset identity into pricing instrument payloads as part of this binding design.
- runtime model `.register()` for platform-managed tables.
