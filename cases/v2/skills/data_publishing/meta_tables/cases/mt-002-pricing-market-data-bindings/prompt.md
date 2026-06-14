You are designing a pricing source-selection layer for a Main Sequence project.

Pricing needs named published-data sets such as `default`, `eod`, `live`, and `risk_manager`.
Each set binds a concept key, such as `discount_curves` or `interest_rate_index_fixings`, to the backend storage table UID of a published DataNode.

The user asks:

"Design the MetaTables and governed operations for this. I want pricing code to select a source set by key and then resolve the right DataNode storage table. Do not confuse this with curve observations or fixing observations."
