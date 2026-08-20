A strong answer should include a snippet like this:

```text
jobs:
  - name: "Vendor Prices"
    execution_path: "scripts/vendor_prices_launcher.py"
    task_schedule:
      type: "crontab"
      expression: "0 6 * * 1-5"
    related_image_id: 77
    cpu_request: "0.25"
    memory_request: "0.5"
```

It should also make these points explicit:
- Uses a top-level `jobs` list
- Uses a weekday crontab expression
- Includes `related_image_id`
- Keeps execution_path relative to the repo root
