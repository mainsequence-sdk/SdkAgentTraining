A strong answer should include a snippet like this:

```text
from mainsequence.client import Artifact

artifact = Artifact.upload_file(
    filepath="vendor_prices_2026_03_15.csv",
    name="vendor_prices_2026_03_15.csv",
    bucket_name="vendor_prices",
    created_by_resource_name="vendor-upload-job",
)
```

It should also make these points explicit:
- Uses `Artifact.upload_file()`
- Includes `filepath`
- Includes `name`
- Includes `bucket_name`
- Includes `created_by_resource_name`
