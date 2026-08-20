You are designing a complete data-publishing mini-project for risk analytics.

Existing canonical table:

- `AssetTable`, where assets are keyed by `uid` and `unique_identifier`

New durable reference state:

- `RiskModelTable`: one row per risk model, keyed by `unique_identifier`
- `RiskScenarioTable`: one row per scenario owned by a risk model, keyed by `(risk_model_uid, scenario_key)`

New time-indexed published facts:

- `RiskScoreStorage`: rows keyed by `time_index`, `asset_identifier`, `risk_model_identifier`, and `scenario_key`
- published columns: `risk_score`, `risk_bucket`, `exposure_value`, `model_version`

The user asks:

"Design the whole thing correctly. I want durable reference state, time-indexed published facts, safe schema lifecycle, and a production validation plan. This should be hard to get wrong in production."
