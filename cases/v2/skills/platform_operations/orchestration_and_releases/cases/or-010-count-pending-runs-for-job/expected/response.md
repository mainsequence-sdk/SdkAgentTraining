The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs runs list 91 --json | jq '[.[] | select(.status == "PENDING")] | length'
```

Why:

The documented runs list command returns job-run objects; filtering by `status == "PENDING"` answers the state-specific question.

Weak answers should be rejected if they:
- count all runs
- filter the wrong status
- use jobs list instead of runs list
