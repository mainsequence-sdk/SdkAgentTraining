The answer should classify `POLYGON_API_KEY` as a secret.

Strong command example:

```bash
mainsequence secrets create POLYGON_API_KEY your-secret-value
```

Strong explanation elements:

- `POLYGON_API_KEY` is a protected credential
- leaking it would create an incident or exposure
- it should not be downgraded into a `Constant`

Weak answers should be rejected if they:

- use `mainsequence constants create ...`
- describe the key as ordinary non-sensitive runtime configuration
