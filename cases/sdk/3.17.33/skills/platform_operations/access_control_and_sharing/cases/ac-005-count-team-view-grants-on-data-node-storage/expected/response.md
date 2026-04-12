The answer should inspect view access on the DataNodeStorage and count the team entries from structured output.

Strong command example:

```bash
mainsequence data-node can_view 42 --json | jq '.teams | length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence data-node can_view 42`
- request `--json`
- count `.teams` from the returned payload

Weak answers should be rejected if they:

- inspect `can_edit` instead of `can_view`
- count rows from the rendered terminal tables
- count users when the question is specifically about teams
