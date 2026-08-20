The answer should use the project jobs list command and count structured results.

Strong command example:

```bash
mainsequence project jobs list --json | jq 'length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence project jobs list`
- request `--json`
- count the returned job objects

Weak answers should be rejected if they:

- use job runs instead of jobs
- count formatted table rows
- omit the counting step
