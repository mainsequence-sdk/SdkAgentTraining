You are adding a new publisher to a Main Sequence project.

A vendor provides daily risk scores for known assets. The published table should be keyed by:

- `time_index`
- `asset_identifier`

where `asset_identifier` is the canonical asset `unique_identifier`, not the vendor ticker.

Columns should include:

- `risk_score`
- `risk_bucket`
- `model_version`

The user asks:

"Design the DataNode and storage contract. I care that this follows the current SDK pattern and could become a stable production table. Explain what code structure you would create and what validations matter."
