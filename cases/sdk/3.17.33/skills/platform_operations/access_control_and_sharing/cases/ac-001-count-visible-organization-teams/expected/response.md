The answer should use the organization teams listing command and count structured results.

Strong command example:

```bash
mainsequence organization teams list --json | jq 'length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence organization teams list`
- request `--json`
- count the returned items programmatically

Weak answers should be rejected if they:

- count rows from the default human table output
- use a different resource surface such as `project` or `data-node`
- omit the counting step
