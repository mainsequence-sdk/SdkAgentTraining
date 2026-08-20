A platform-managed MetaTable named `RiskModelTable` already exists in production and is owned by provider `risk_app.migrations:migration`.

The current model has:

- `uid`
- `unique_identifier`
- `display_name`

The user now wants to add:

- nullable `status`
- nullable `metadata` JSON
- lookup index on `status`

A teammate suggests editing the original migration file and then calling `RiskModelTable.register()` again at application startup.

The user asks:

"What is the correct lifecycle for this contract change? Include the commands, what should be verified, and what we must not do."
