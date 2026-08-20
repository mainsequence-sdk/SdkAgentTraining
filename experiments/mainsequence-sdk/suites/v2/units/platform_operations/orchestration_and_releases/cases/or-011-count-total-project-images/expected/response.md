The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project images list --json | jq 'length'
```

Why:

`project images list` is the documented image inventory command, and `--json` makes the total count easy to compute.

Weak answers should be rejected if they:
- count only ready images when total was asked
- use resource commands instead of image commands
- count terminal rows
