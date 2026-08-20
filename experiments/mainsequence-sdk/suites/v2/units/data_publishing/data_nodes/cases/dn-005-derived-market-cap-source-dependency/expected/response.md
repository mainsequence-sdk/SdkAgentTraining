The answer should describe a derived DataNode with an explicit source dependency.

Required points:

- The output storage is a time-indexed asset table keyed by `(time_index, asset_identifier)` where the asset is the market-cap/base asset.
- The source bars are an explicit dependency, either an existing node object or an APIDataNode built from a registered table UID.
- Exactly one source path should be accepted; accepting both or neither is an error.
- The node should map each source tradable instrument to its output market-cap asset deterministically.
- Static supply anchors are runtime/update inputs used to calculate `market_cap = close * supply`; they are not separate time-series dependencies unless the task explicitly makes them time-varying.
- Incremental windows are based on the last update for the output market-cap asset, then translated back to the corresponding source instrument range.
- The source read should be scoped with a dimension/range map instead of reading the entire source table.
- The output should keep observation columns such as `market_cap`, `price`, and `volume`, with no source UID or policy fields as row data.
- The DataFrame must use UTC nanosecond `time_index`, canonical asset identity, lowercase concise columns, no datetime payload columns, and no duplicate keys.
- If no source rows or no supply anchor is available, return an empty DataFrame for that slice or run rather than `None`.

Common wrong answers:

- Creating the source bars dependency inside the update loop.
- Publishing rows keyed by `BTC/USDT` when the dataset is market-cap by base asset.
- Treating static supply as a hidden mutable global that changes dataset meaning without review.
- Reading all historical bars on every run.
- Mixing source table UID, source cadence, or policy fields into observation columns.
