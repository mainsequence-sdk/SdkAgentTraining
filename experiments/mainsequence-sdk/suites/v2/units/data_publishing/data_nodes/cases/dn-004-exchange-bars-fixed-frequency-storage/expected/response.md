The answer should design a storage-first DataNode workflow.

Required points:

- Use a time-indexed storage contract per supported bar family and frequency.
- Keep the supported frequency set finite and migration-owned; adding a new frequency requires a schema migration before the node can run it.
- The storage grain is `(time_index, asset_identifier)` where `asset_identifier` is the canonical asset `unique_identifier`, not an exchange ticker.
- Declare cadence on each frequency-specific storage class and keep table identity stable.
- Put OHLCV, volume, trade count, VWAP, open-time, or imbalance payload columns in storage as real observations with concise lowercase names.
- Include an asset foreign key to the canonical asset identity and meaningful table/column metadata.
- Make frequency a dataset-meaning field. Treat asset category, explicit asset list, raw mirror location, worker count, memory budget, and chunk size according to whether they change dataset meaning or only updater/runtime behavior.
- Resolve asset scope before update; fail clearly when neither explicit assets nor category scope is available.
- Use per-asset last-update state to compute bounded update windows and respect a limit-update time when present.
- Return `pd.DataFrame()` for no active assets, no available files, or no pending ranges.
- Build output with a UTC nanosecond `time_index` first and `asset_identifier` second; de-duplicate and sort rows before returning.
- Avoid creating storage classes or registering storage ad hoc during `update()`.
- Route schema creation and new frequency support through the MetaTable migration workflow.

Common wrong answers:

- Creating tables dynamically inside the update loop.
- Treating exchange tickers as the persisted asset identity.
- Letting unsupported frequencies create new storage automatically.
- Returning `None` when there are no rows.
- Putting runtime mirror paths or memory limits into row columns.
- Fetching full history on every run.
