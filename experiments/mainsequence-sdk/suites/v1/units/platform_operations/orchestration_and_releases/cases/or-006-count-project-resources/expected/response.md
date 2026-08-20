The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --json | jq 'length'
```

Why:

`project project_resource list` is the documented resource listing surface and `--json` lets you count the returned resource objects safely.

Weak answers should be rejected if they:
- count terminal rows
- use jobs or images commands instead of resources
- omit the counting step
