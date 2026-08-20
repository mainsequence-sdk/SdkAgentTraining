The answer should design a migration-first workflow with shared history.

Required points:

- Keep one full provider with a shared Alembic version table, script location, version location prefix, registry, and project namespace.
- Build scoped providers by changing only the `metatable_models` and target metadata for the selected model subset.
- Scoped revisions must chain into the same history/version table as the full provider; they should not create unrelated migration streams.
- Scope resolution should accept named groups or explicit table identifiers and deduplicate models.
- Include canonical dependency table metadata only so FKs can be generated; exclude those dependency tables and their constraints from migration operations.
- For optional bar storage, only selected finite frequencies should be included in a scoped provider.
- For source-dependent derived storage, build the storage class from explicit source metadata such as source table UID, source cadence, output frequency, and interpolation rule.
- The dynamic provider should fail before autogenerate or execution if required source metadata is missing.
- Before running the dependent workflow, verify the dynamic storage exists and is bound to the registered backend row.
- Use documented `mainsequence migrations current`, `revision`, and `upgrade` provider lifecycle commands or a thin wrapper that calls the SDK command with the selected provider.
- Do not use direct table `.register()`, hand-written backend payloads, multiple unrelated version tables, or runtime DDL inside the DataNode/portfolio workflow.

Common wrong answers:

- Adding every optional bar table to the default provider.
- Creating one migration history per scope.
- Migrating canonical dependency tables owned by another package just to satisfy FKs.
- Letting dynamic storage be created when the DataNode starts.
- Continuing when source table UID or cadence cannot be resolved.
