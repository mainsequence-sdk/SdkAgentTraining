The answer should use the organization-visible project command and count structured results.

Strong command example:

```bash
mainsequence organization project-names --json | jq 'length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence organization project-names`
- request `--json`
- count the returned items from structured output

Weak answers should be rejected if they:

- use `mainsequence project list` instead of the organization-visible project-names command
- count terminal table rows
- omit the counting step
