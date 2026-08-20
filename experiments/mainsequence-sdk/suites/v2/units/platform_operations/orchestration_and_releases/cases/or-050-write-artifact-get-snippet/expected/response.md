A strong answer should include a snippet like this:

```text
import pandas as pd
from mainsequence.client import Artifact

source_artifact = Artifact.get(
    bucket__name="vendor_prices",
    name="vendor_prices_2026_03_15.csv",
)

df = pd.read_csv(source_artifact.content)
```

It should also make these points explicit:
- Uses `Artifact.get()`
- Identifies the bucket and artifact name
- Reads from `source_artifact.content`
- Shows pandas loading from the Artifact handle
