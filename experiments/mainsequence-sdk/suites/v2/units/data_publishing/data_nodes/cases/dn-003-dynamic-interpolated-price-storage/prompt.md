You are designing an interpolated price publisher for a Main Sequence project.

Input:

- an explicit source price `DataNode` or `APIDataNode`
- source storage table UID
- source cadence, such as `1d` or `5m`
- requested upsample frequency, such as `1d` or `15m`
- interpolation rule, such as `ffill` or `session_close`
- asset scope

Output rows should be keyed by:

- `time_index`
- `asset_identifier`

Output columns include OHLCV fields plus `interpolated`.

The user asks:

"Design this DataNode correctly. The output storage table identity must change when the source table UID, source cadence, upsample frequency, or interpolation rule changes. Do not hide the source dependency or put storage policy into row columns."
