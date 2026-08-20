A strong answer should include a snippet like this:

```text
jobs:
  - name: "Simulated Prices"
    execution_path: "scripts/simulated_prices_launcher.py"
    task_schedule:
      type: "crontab"
      expression: "0 0 * * *"
    related_image_id: 77
    cpu_request: "0.25"
    memory_request: "0.5"
```

It should also make these points explicit:
- Uses a top-level `jobs` list
- Uses `execution_path`
- Uses `task_schedule` with `type` and `expression`
- Includes `related_image_id`
- Includes valid compute fields
