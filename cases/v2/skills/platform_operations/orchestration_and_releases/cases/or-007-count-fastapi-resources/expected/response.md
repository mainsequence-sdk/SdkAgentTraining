The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --filter resource_type=fastapi --json | jq 'length'
```

Why:

The documented project resource list command supports resource-type filters and `--json` makes the count deterministic.

Weak answers should be rejected if they:
- omit the resource_type filter
- count all resources
- count table rows
