A strong answer should include a snippet like this:

```text
jobs:
  - name: "Job A"
    execution_path: "scripts/job_a.py"
    task_schedule:
      type: "crontab"
      expression: "0 0 * * *"
    related_image_id: 77
  - name: "Job B"
    execution_path: "scripts/job_b.py"
    task_schedule:
      type: "interval"
      every: 1
      period: "hours"
    related_image_id: 77
```

It should also make these points explicit:
- Uses one top-level `jobs` list
- Defines each job separately
- Uses valid schedule objects
- Keeps both jobs eligible for one shared selected image in batch flow
