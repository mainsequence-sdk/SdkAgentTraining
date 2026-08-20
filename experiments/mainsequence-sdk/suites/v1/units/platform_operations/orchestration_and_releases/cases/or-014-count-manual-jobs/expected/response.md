The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs list --json | jq '[.[] | select(.task_schedule == null)] | length'
```

Why:

Manual jobs show up in the jobs list without a schedule object, so the right structured check is `task_schedule == null`.

Weak answers should be rejected if they:
- use runs instead of jobs
- filter on an invented mode field
- count all jobs
