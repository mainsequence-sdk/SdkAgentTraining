You are modeling current account details returned by a crypto exchange API.

Canonical accounts already exist. The exchange returns different detail fields for spot and futures accounts. The detail payload includes permissions, commission settings, account status flags, update time, and an API-key fingerprint. It must never store the raw API key or secret. Timestamped balances and positions will be published elsewhere.

The user asks:

"Design the table contracts for this account metadata. I want the current account details to be queryable and safe, but I do not want credentials or balance history mixed into the table."
