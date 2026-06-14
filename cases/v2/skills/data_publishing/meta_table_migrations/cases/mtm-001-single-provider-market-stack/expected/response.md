The response should recommend one SDK-managed Alembic provider when the three import roots are one logical market stack with shared relationships and one schema lifecycle.

It should use the SDK helper pattern:

- `build_alembic_version_metatable(...)`.
- `build_metatable_model_registry(...)` or an explicit registry helper that imports the three model sources and de-duplicates them.
- `build_metatable_migration_provider(...)`.
- SDK-owned `run_mainsequence_alembic_env(...)` and `script.py.mako` in the generated migration package.

The provider should define:

- package, for example `market_core` or the distribution's canonical package.
- migration namespace, for example `market-stack`.
- script location, for example `migrations:`.
- target metadata from the shared declarative base.
- `alembic_registry` pointing to the Alembic version MetaTable class.
- `metatable_models` containing provider-scoped models from core, portfolios, and pricing.

The answer should include CLI commands:

```bash
mainsequence migrations current --provider migrations:migration
mainsequence migrations revision --provider migrations:migration -m "add market stack metatables"
mainsequence migrations upgrade --provider migrations:migration head
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

It should explain that:

- `current` verifies provider import and current revision state.
- `revision` writes normal Alembic files.
- `upgrade` reserves provider MetaTables, runs Alembic DDL through backend-issued migration credentials, finalizes provider-scoped MetaTable catalog rows, and runs any optional provider hook.
- parent and child models with FKs must be included in the provider scope so Alembic can render the graph.
- runtime startup must attach already-registered MetaTables and TimeIndexMetaTables; it must not create schema or call model `.register()`.

The response should reject:

- separate `market_portfolios.migrations:migration` and `market_pricing.migrations:migration` providers unless the user defines a real independent lifecycle boundary.
- scanning all imported packages implicitly.
- direct model `.register()` calls for platform-managed models.
- hand-rolled backend request payloads or fake operation lists.
- threading `data_source_uid` through migration status or apply commands.
