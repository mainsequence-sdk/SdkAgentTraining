The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs runs list 91 --json
```

Why:

`jobs runs list` is the documented run-history surface, and `--json` makes the returned runs scriptable.

Weak answers should be rejected if they:
- use jobs list instead of runs list
- omit the job id
- inspect logs instead of run history
