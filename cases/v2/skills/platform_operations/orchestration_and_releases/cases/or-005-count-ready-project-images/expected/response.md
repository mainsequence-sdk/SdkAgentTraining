The answer should list project images, filter to ready images, and count the filtered results.

Strong command example:

```bash
mainsequence project images list --json | jq '[.[] | select(.is_ready == true)] | length'
```

Equivalent structured counting approaches are acceptable if they:

- use `mainsequence project images list`
- request `--json`
- filter on readiness
- count the filtered image objects

Weak answers should be rejected if they:

- count all images without checking readiness
- omit `--json`
- count rendered table rows
