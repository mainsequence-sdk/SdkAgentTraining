You are designing account allocation state for a Main Sequence project.

Existing canonical tables:

- `AccountTable`, keyed by `uid` and `unique_identifier`
- `PortfolioTable`, keyed by `uid` and `unique_identifier`
- `AssetTable`, keyed by `uid` and `unique_identifier`

The user needs durable configuration for:

- allocation models such as `conservative`, `growth`, and `dollar_neutral`
- assigning one or more accounts to an allocation model over time
- target rows inside an allocation model that can point either to an asset or a portfolio
- each target row must define exactly one exposure policy: `weight_notional_exposure`, `constant_notional_exposure`, or `single_asset_quantity`

Time-indexed realized target-position facts will be published later by a DataNode.

The user asks:

"Design the MetaTable side. I need durable configuration that is safe to query, safe to evolve, and clear about ownership and exclusivity. Do not mix this with the future DataNode output."
