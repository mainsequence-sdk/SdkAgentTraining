You are adding a derived time series for crypto market capitalization.

The source data is a bar series keyed by tradable instruments such as `BTC/USDT`. The new series should be keyed by the base crypto asset, such as `BTC`, because downstream portfolio logic consumes market-cap values at the asset level. Current circulating supply is available as a static per-asset anchor.

The source bars may be provided as an already-built node object or as a registered source table UID.

The user asks:

"Design the DataNode correctly. It should reuse the source bars, publish only the derived series, and update incrementally without confusing tradable instrument identity with the output asset identity."
