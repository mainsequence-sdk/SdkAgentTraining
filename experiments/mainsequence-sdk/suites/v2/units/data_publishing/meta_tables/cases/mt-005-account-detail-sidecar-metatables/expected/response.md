The answer should model account metadata as sidecar MetaTables.

Required points:

- Link each sidecar row to a canonical account, ideally with the canonical `account_uid` as both primary key and FK.
- Use separate tables when spot and futures account contracts diverge.
- Store current account metadata such as account family, venue, account type, status flags, update time, permissions, commissions, and API key fingerprint.
- Never store raw API keys or API secrets; only a fingerprint or secret reference belongs in durable metadata.
- Keep balances, positions, fills, and other timestamped account facts out of these tables.
- Add uniqueness or lookup support for canonical account unique identifier and key fingerprint as appropriate.
- Use project-prefixed naming, stable logical identity, table descriptions, and column metadata.
- Use an intentional delete policy from canonical account to sidecar details.
- Route creation and contract evolution through the migration provider.
- Runtime services should attach/read the migrated table and fail clearly when it is not registered.

Common wrong answers:

- Combining spot and futures-specific fields into one ambiguous unvalidated table.
- Storing raw API credentials.
- Publishing balances/positions in the sidecar instead of time-indexed facts.
- Registering the tables directly during application startup.
- Keying rows by API key fingerprint instead of canonical account identity.
