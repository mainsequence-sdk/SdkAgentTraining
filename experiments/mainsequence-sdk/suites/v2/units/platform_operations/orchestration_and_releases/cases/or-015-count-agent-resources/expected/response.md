The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --filter resource_type=agent --json | jq 'length'
```

Why:

Agent resources are listed through the documented project resource surface and can be narrowed with the resource type filter.

Weak answers should be rejected if they:
- use agent runtime list instead of project resources
- omit the filter
- count rendered rows
