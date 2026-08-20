The response should say these are durable row-oriented reference tables and should be modeled as platform-managed MetaTables, not DataNodes. DataNodes would be appropriate for update processes that publish time-indexed fact observations, not for canonical calendar identity and relational reference state.

It should define a relational graph similar to:

- `CalendarTable`: one row per calendar, with UUID primary key and stable `unique_identifier` business key.
- `CalendarDateTable`: one row per calendar and date, with FK to `CalendarTable.uid` or another clearly justified durable calendar key.
- `CalendarSessionTable`: one row per concrete trading session, with FK to the owning calendar/date row.
- `CalendarEventTable`: one row per holiday, early close, closure, or ad hoc event, with FK to the calendar or calendar date depending on event grain.

The answer should require:

- `PlatformManagedMetaTable` plus a shared project/domain declarative base.
- explicit project-prefixed `__tablename__`, preferably via `schema_table_name(...)`.
- `schema=None` for the default PostgreSQL schema, not `schema="public"`.
- `__metatable_identifier__` and intention-rich `__metatable_description__` for each model.
- `mapped_column(info={"label": ..., "description": ...})` on every mapped column.
- UUID primary keys for durable row identity.
- stable business keys such as `unique_identifier`, `calendar_date`, `session_identifier`, or `event_identifier` where idempotent upsert or lookup is needed.
- unique indexes or constraints for idempotent keys, including composite uniqueness such as `(calendar_uid, calendar_date)`, `(calendar_date_uid, session_identifier)`, or another equivalent grain.
- lookup indexes for common filters such as calendar UID, date, event type, status, or source.
- SQLAlchemy `ForeignKey` or `ForeignKeyConstraint` declarations, not prose-only relationships.
- `ondelete="RESTRICT"` for canonical parent rows when dependent rows should prevent accidental deletion.
- `ondelete="CASCADE"` only for dependent child or membership rows when lifecycle ownership is explicit.

The response should route schema lifecycle to the migration skill:

```bash
mainsequence migrations current --provider <package>.migrations:migration
mainsequence migrations revision --provider <package>.migrations:migration -m "add calendar metatables"
mainsequence migrations upgrade --provider <package>.migrations:migration head
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

It should say to include all parent and child models in the selected provider's `metatable_models` so Alembic can render FK and index DDL and the SDK can finalize provider-scoped MetaTable catalog rows.

The response should explicitly reject:

- modeling this reference graph as a DataNode.
- calling model `.register()` in runtime startup for platform-managed tables.
- using raw SQL table creation outside the SDK migration workflow.
- encoding FK target MetaTable UIDs in model config.
- relying only on ORM `relationship(...)` without database-level FKs and constraints.
