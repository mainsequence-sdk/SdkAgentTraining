The answer should use the correct CLI surface and a structured counting or filtering path.

Strong command example:

```bash
mainsequence project images create --timeout 600 --poll-interval 15
```

Why:

The documented image-create command supports `--timeout` and `--poll-interval` for longer readiness polling.

Weak answers should be rejected if they:
- invent a separate wait command
- omit image creation
- use unsupported flags
