The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs runs list 91 --json | jq 'length'
```

Why:

`project jobs runs list 91` is the documented run-history surface for one job, and `--json` lets you count runs directly.

Weak answers should be rejected if they:
- use jobs list instead of runs list
- omit the job id
- count table rows
