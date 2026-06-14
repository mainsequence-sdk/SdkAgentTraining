# data_publishing/data_nodes

Case set version: `v2`

This folder contains authored evaluation cases for this skill.

SDK compatibility is resolved through `sdk/<sdk-version>/case-map.yaml`.

Target SDK snapshot: `sdk/4.4.5/skills/data_publishing/data_nodes/source/SKILL.md`.

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
