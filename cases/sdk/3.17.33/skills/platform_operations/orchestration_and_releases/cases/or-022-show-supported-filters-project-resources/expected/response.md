The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project project_resource list --show-filters
```

Why:

The documented `--show-filters` flag is the right way to inspect supported filters before automating around a list command.

Weak answers should be rejected if they:
- guess filter names from memory
- use raw grep over help text
- list resources without inspecting filters
