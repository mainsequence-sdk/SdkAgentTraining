The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project images list --show-filters
```

Why:

The documented `--show-filters` flag is the right way to inspect supported image filters before automating against them.

Weak answers should be rejected if they:
- guess image filter names from memory
- skip filter inspection
- use unrelated help output instead
