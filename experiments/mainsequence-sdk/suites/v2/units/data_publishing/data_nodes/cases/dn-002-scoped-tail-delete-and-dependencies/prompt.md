You are reviewing a proposed DataNode implementation for account-level holdings facts.

The proposed design says:

- the upstream price source is built dynamically from whatever asset list appears in the latest holdings file.
- the source price storage class is passed as a constructor-only argument, not stored in config.
- cleanup uses a compiled SQL operation:
  `DELETE FROM account_holdings_storage WHERE account_uid = :account_uid`
- if the user wants to rebuild all rows for one account, the implementation calls:
  a full-history deletion with no account-level dimension filter.
- the output frame sometimes uses `pd.Timestamp.now("UTC").normalize()` directly for `time_index`.

The user asks:

"Review this design and tell me what must change before it is acceptable under the current SDK. Focus on source dependency modeling, scoped cleanup, and time index handling."
