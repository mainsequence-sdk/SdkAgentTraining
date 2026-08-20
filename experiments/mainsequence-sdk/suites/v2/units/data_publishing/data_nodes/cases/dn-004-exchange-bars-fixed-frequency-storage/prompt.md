You are designing bar publishers for a crypto exchange integration.

The project needs two bar families:

- exchange-provided OHLCV bars
- trade-derived time bars built from raw trade files

Users can choose a frequency such as `1m`, `5m`, `1h`, or `1d`. The project should only run frequencies that are already part of the managed schema. The updater can receive either an explicit asset list or a current asset category. Raw zip files may come from a local mirror, object-storage mirror, or the exchange's public file endpoint.

The user asks:

"Design this so it is production-safe. I want predictable storage, repeatable updates, bounded memory behavior, and a clear failure mode when a frequency or asset scope is not ready."
