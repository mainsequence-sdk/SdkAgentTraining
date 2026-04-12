The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs run 91
```

Why:

`project jobs run` is the documented command for triggering a manual run for an existing job.

Weak answers should be rejected if they:
- create a new job instead of running the existing one
- use runs list instead of run
- invent a start command
