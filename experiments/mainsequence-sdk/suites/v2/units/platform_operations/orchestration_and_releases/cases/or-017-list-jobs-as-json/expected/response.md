The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project jobs list --json
```

Why:

`project jobs list --json` is the documented structured-output path for project jobs and is appropriate for downstream scripting.

Weak answers should be rejected if they:
- omit --json
- use runs instead of jobs
- count terminal output
