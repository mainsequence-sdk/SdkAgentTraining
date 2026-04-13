The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project images list --filter project_repo_hash__in=4a1b2c3d --json | jq 'length'
```

Why:

The images list command supports filters and `project_repo_hash__in` is the documented shape for narrowing results to a specific commit hash.

Weak answers should be rejected if they:
- omit the filter
- use an unsupported ad hoc grep over table output
- count all images
