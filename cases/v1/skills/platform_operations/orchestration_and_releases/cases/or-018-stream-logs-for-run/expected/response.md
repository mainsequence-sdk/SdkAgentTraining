The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs runs logs 501 --max-wait-seconds 900
```

Why:

`jobs runs logs` is the documented log-inspection command and `--max-wait-seconds 900` matches the standard long-poll verification flow in the docs.

Weak answers should be rejected if they:
- use runs list instead of logs
- inspect only job metadata
- invent a non-existent logs command
