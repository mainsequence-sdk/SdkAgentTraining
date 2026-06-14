The response should say this is an in-place contract evolution for an existing platform-managed MetaTable and belongs to the SDK MetaTable migration lifecycle.

The correct lifecycle:

1. Update the SQLAlchemy model declaration for `RiskModelTable` with the new nullable `status` and `metadata` JSON columns, full column `info` metadata, and the `status` lookup index.
2. Confirm the selected provider is `risk_app.migrations:migration` and that `RiskModelTable` remains in the provider's `metatable_models`.
3. Check current state:

```bash
mainsequence migrations current --provider risk_app.migrations:migration
```

4. Create a new Alembic revision on top of current head:

```bash
mainsequence migrations revision --provider risk_app.migrations:migration -m "add risk model status metadata"
```

If the answer chooses `--autogenerate`, it must also include the explicit
`--sqlalchemy-url` required by the SDK workflow and explain the baseline
database being inspected.

5. Review the generated revision to confirm it adds the two columns and status index and does not recreate unrelated tables.
6. Apply:

```bash
mainsequence migrations upgrade --provider risk_app.migrations:migration head
```

7. Verify SQL apply and provider-scoped catalog finalization. The backend MetaTable catalog binding for `RiskModelTable` should refresh after upgrade.
8. Runtime startup should attach the already-migrated model. It must not create schema or register the model.

The response should explicitly reject:

- editing an already-applied migration file.
- calling `RiskModelTable.register()` in application startup.
- trying to apply the contract change through normal registration again.
- hand-authoring backend migration request bodies.
- threading `data_source_uid` through migration status or apply commands.
- claiming success before both Alembic SQL execution and catalog sync/finalization have succeeded.

It should explain that old revisions are immutable because deployed databases may already reference them in their Alembic version table. Any follow-up schema change needs a new revision on top of the current head.
