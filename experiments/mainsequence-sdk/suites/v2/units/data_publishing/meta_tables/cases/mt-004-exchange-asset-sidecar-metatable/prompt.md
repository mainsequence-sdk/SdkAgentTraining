You are modeling exchange-specific asset metadata for a Main Sequence project.

Canonical assets already exist in the platform. The exchange adds details such as trading symbol, asset family, venue, market type, status, base and quote asset references, contract metadata, and the time the source payload was retrieved.

The user asks:

"Design the durable table for this. I do not want to duplicate canonical assets or turn current reference metadata into a time-series publisher. It needs to be reliable for lookups and safe to evolve."
