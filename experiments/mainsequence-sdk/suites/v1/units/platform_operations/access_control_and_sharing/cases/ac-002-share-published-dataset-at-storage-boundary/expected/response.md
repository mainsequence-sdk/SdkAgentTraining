The answer should identify the published table boundary, not the Python producer class.

Strong answer elements:

- the real shareable resource is `DataNodeStorage`
- readers should usually receive `view`
- the inspection command is:

```bash
mainsequence data-node can_view <DATA_NODE_STORAGE_ID>
```

- the explanation distinguishes:
  - the Python `DataNode` class defines how data is produced
  - the `DataNodeStorage` is the published dataset other users consume

Weak answers should be rejected if they:

- say to share "the DataNode code"
- default readers to `edit`
- omit the access inspection step
