# data_publishing/data_nodes

Case set version: `v2`

This folder contains authored evaluation cases for this skill.

Target/suite compatibility is resolved through `experiments/mainsequence-sdk/compatibility/`.

Target SDK snapshot: `https://github.com/mainsequence-sdk/mainsequence-sdk/blob/3b5a20a344cec0c960351dc3c601d32a66a8b46e/agent_scaffold/skills/data_publishing/data_nodes/SKILL.md`.

## Cases

- `dn-001-asset-risk-score-storage-first`
  Tests storage-first DataNode construction for daily asset risk scores with a
  `PlatformTimeIndexMetaTable` storage contract, asset foreign key, cadence,
  config discipline, and incremental update behavior.
- `dn-002-scoped-tail-delete-and-dependencies`
  Tests review behavior for a DataNode that has hidden dependencies, stale
  cleanup logic, raw SQL deletes, and unsafe unscoped deletion.
- `dn-003-dynamic-interpolated-price-storage`
  Difficult DataNode case for dynamic `PlatformTimeIndexMetaTable` storage
  identity, source DataNode dependencies, cadence validation, asset-scoped
  incremental updates, and generated storage table boundaries.
- `dn-004-exchange-bars-fixed-frequency-storage`
  Difficult DataNode case for exchange bar publishers with finite migrated
  frequency storage, raw-file update execution, per-asset incrementality, and
  runtime memory controls.
- `dn-005-derived-market-cap-source-dependency`
  Difficult DataNode case for a derived market-cap series that depends on source
  bars, transforms source instrument identity to output asset identity, and uses
  scoped incremental source reads.
