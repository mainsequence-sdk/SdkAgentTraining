# data_publishing/meta_table_migrations

Authored case bank for `data_publishing/meta_table_migrations` in case set `v2`.

Target SDK snapshot: `sdk/4.4.5/skills/data_publishing/meta_table_migrations/source/SKILL.md`.

Migration status: pending revalidation against the target SDK.

## Cases

- `mtm-001-single-provider-market-stack`
  Tests provider setup for a market stack where one SDK Alembic provider covers
  core, portfolio, and pricing MetaTable models.
- `mtm-002-contract-change-migration-lifecycle`
  Tests schema-change lifecycle for an existing platform-managed MetaTable,
  including current/revision/upgrade commands, immutable old revisions, and
  attach-only runtime behavior.
- `mtm-003-market-risk-data-publishing-graph`
  Difficult integrated case combining relational MetaTables, DataNode storage,
  storage foreign keys, indexes, one migration provider, DataNode update
  boundaries, and runtime attach-only behavior.
