You are setting up MetaTable migration infrastructure for a Main Sequence package.

The package has three import roots:

- `reference_core`
- `portfolio_workflows`
- `pricing_engine`

All three define platform-managed MetaTable models and DataNode storage classes that share relationships. The user asks:

"Set up the migration approach. I do not want three unrelated migration systems unless that is actually required. Explain how this should be managed as code, how I would apply it, and where application runtime code should stop."
