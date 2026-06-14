# data_publishing/meta_tables

Authored case bank for `data_publishing/meta_tables` in case set `v2`.

Target SDK snapshot: `sdk/4.4.5/skills/data_publishing/meta_tables/source/SKILL.md`.

Migration status: pending revalidation against the target SDK.

## Cases

- `mt-001-calendar-relational-metatables`
  Tests relational MetaTable modeling for calendar reference data, including row
  grain, business keys, foreign keys, indexes, delete semantics, and migration
  routing.
- `mt-002-pricing-market-data-bindings`
  Tests MetaTable design for pricing market-data source selection, including
  concept bindings to DataNode storage UIDs, uniqueness, lookup indexes, and
  governed compiled SQL operations.
- `mt-003-account-portfolio-target-relations`
  Difficult relational-modeling case for account-to-portfolio target allocation
  state, including ownership, join tables, composite uniqueness, FK targets,
  delete behavior, and constraints that should not be pushed into DataNodes.
