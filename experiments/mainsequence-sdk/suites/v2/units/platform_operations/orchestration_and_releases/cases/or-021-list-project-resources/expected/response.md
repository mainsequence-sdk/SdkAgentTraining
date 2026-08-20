The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --json
```

Why:

`project project_resource list` is the documented project-resource surface and `--json` is the right path for structured inspection.

Weak answers should be rejected if they:
- use release creation commands instead of listing
- use images list instead of resources
- omit structured output
