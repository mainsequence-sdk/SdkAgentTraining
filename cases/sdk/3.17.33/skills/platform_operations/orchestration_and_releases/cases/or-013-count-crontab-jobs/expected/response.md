The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs list --json | jq '[.[] | select(.task_schedule.type == "crontab")] | length'
```

Why:

The jobs list command returns structured schedule data; filtering `task_schedule.type` isolates crontab jobs.

Weak answers should be rejected if they:
- use runs instead of jobs
- count all jobs
- omit structured filtering
