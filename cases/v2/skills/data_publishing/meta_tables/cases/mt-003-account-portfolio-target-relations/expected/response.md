The answer should keep durable allocation configuration in MetaTables and explicitly separate it from future time-indexed target-position facts, which belong to DataNode storage.

Expected relational graph:

- `AccountAllocationModelTable`: one row per allocation model, with UUID primary key, stable `unique_identifier`, display fields, status/source metadata, and unique index on `unique_identifier`.
- `AccountTargetAllocationTable`: relationship/history table assigning an account to an allocation model, with FK to `AccountTable.uid`, FK to `AccountAllocationModelTable.uid`, effective date fields or status fields as needed, and composite uniqueness appropriate to the intended assignment grain.
- `AllocationTargetTable` or equivalent: one row per target inside an allocation model, with FK to `AccountAllocationModelTable.uid`, target type, nullable asset FK, nullable portfolio FK, and exposure columns.

The response should require database-level constraints:

- FK to `AccountTable.uid` for account ownership.
- FK to `AccountAllocationModelTable.uid` for allocation model ownership.
- FK to `AssetTable.uid` for asset targets.
- FK to `PortfolioTable.uid` for portfolio targets.
- Composite uniqueness for membership/relationship grains, such as `(account_uid, allocation_model_uid, effective_start)` or a clearly justified alternative.
- Unique target identity inside an allocation model when target rows must be idempotent.
- Lookup indexes for account, allocation model, target type, asset, portfolio, status, and effective dates.
- Check-constraint or equivalent SQLAlchemy-level constraint requiring exactly one target identity branch when target type is asset versus portfolio.
- Check-constraint or equivalent rule requiring exactly one exposure policy column to be populated.

Delete semantics should be intentional:

- `RESTRICT` for canonical account, asset, portfolio, and allocation model rows when dependent rows should prevent accidental deletion.
- `CASCADE` only for rows whose lifecycle is strictly owned by a parent, such as allocation target rows owned by an allocation model, if the project explicitly wants target rows removed with the model.

The answer should require:

- `PlatformManagedMetaTable` models.
- project-prefixed physical table names via `schema_table_name(...)`.
- `schema=None` for default PostgreSQL schema.
- `__metatable_identifier__` and intention-rich `__metatable_description__`.
- `mapped_column(info={"label": ..., "description": ...})` for every column.
- migration-provider inclusion for all related models.
- governed compiled SQL operations for upsert/list/resolve workflows, with explicit MetaTable UID scope and read/write access.

The answer should reject:

- putting allocation configuration into a DataNode.
- storing time-indexed realized target positions in these configuration tables.
- using provider symbols or display names as FK targets.
- relying only on application-side validation for uniqueness and exposure constraints.
- calling `.register()` at runtime for platform-managed models.
