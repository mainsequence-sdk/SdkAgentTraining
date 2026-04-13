The answer should keep both steps on the same secret identity.

Strong example:

```bash
mainsequence secrets create POLYGON_API_KEY your-secret-value
```

```python
from mainsequence.vam_client import Secret

Secret.get(name="POLYGON_API_KEY").value
```

Why:

- `Secret` is the correct resource for sensitive credentials
- the CLI creates the named secret
- the SDK reads back the same named secret through `Secret.get(...).value`
