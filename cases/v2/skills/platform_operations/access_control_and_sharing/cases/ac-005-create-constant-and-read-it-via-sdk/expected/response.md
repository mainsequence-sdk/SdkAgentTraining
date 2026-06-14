The answer should keep both steps on the same constant identity.

Strong example:

```bash
mainsequence constants create MODEL__DEFAULT_WINDOW 252
```

```python
from mainsequence.vam_client import Constant

Constant.get(name="MODEL__DEFAULT_WINDOW").value
```

`Constant.get_value("MODEL__DEFAULT_WINDOW")` is also acceptable.

Why:

- `Constant` is the correct resource for non-secret runtime configuration
- the CLI creates the named constant
- the SDK reads back the same named constant
