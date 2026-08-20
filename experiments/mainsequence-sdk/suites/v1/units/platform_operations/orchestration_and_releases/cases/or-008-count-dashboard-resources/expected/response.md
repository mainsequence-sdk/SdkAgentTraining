The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --filter resource_type=dashboard --json | jq 'length'
```

Why:

Dashboard resources are exposed through the same project resource list surface, filtered by resource type.

Weak answers should be rejected if they:
- use release commands instead of resource listing
- omit the dashboard filter
- count rendered rows
