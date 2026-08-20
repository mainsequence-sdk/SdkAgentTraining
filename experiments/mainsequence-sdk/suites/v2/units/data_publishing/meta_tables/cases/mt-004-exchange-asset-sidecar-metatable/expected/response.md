The answer should model this as a migration-managed sidecar MetaTable.

Required points:

- One row should be linked to one canonical asset, using the canonical asset UID as the sidecar primary key or otherwise enforcing one-to-one identity.
- The table should keep the canonical asset identity as the source of truth and store exchange-specific fields as metadata.
- The design should include lookup paths for exchange symbol, asset kind/family, and canonical unique identifier.
- The FK to the canonical asset should use normal SQLAlchemy metadata and an intentional delete behavior.
- The table should use project-prefixed physical naming, stable logical identity, and meaningful table/column metadata.
- Current reference metadata belongs in this sidecar; historical prices, balances, bars, or observations belong in DataNode storage.
- Writes should go through governed repository/compiled operations or well-scoped helpers, not ad hoc SQL.
- Creation and schema changes should be handled by the SDK MetaTable migration workflow, not runtime `.register()`.
- Runtime code should fail clearly if the table has not been migrated or attached before lookup/write operations.

Common wrong answers:

- Adding exchange fields directly to the canonical asset table.
- Keying the table only by mutable ticker/symbol.
- Creating one row per timestamp or storing bars in the sidecar.
- Registering the platform-managed table at application startup.
- Omitting indexes needed for symbol and identity lookup.
