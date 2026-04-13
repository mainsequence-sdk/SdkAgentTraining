The answer should list runs for the job, filter by running status, and count the filtered results.

Strong command example:

```bash
mainsequence project jobs runs list 91 --json | jq '[.[] | select(.status == "RUNNING")] | length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence project jobs runs list 91`
- request `--json`
- filter by `status == "RUNNING"`
- count the filtered runs

Weak answers should be rejected if they:

- use `project jobs list` instead of run history
- count all runs instead of only `RUNNING`
- omit structured filtering
