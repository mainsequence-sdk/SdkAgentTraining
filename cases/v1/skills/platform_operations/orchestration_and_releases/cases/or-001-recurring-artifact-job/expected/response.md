The ideal answer should make these decisions explicit:

1. This is a shared recurring workflow, so it should be represented as code in `scheduled_jobs.yaml`, not as a one-off CLI-created job hidden in shell history.
2. The vendor file should be handled as an `Artifact`, because the operational unit is a file drop rather than a structured table.
3. The scheduled job must be pinned to a project image through `related_image_id` for reproducibility.
4. `--strict` should not be the default here unless the user explicitly intends the YAML file to be the full desired state for project jobs.
5. Success must include verification after creation: list jobs, inspect runs, and inspect logs.

A strong answer will include a batch file like:

```yaml
jobs:
  - name: "Vendor Prices - Weekday 06:00 UTC"
    execution_path: "scripts/vendor_prices_launcher.py"
    task_schedule:
      type: "crontab"
      expression: "0 6 * * 1-5"
    related_image_id: 77
    cpu_request: "0.25"
    memory_request: "0.5"
```

A strong answer will also mention commands in roughly this flow:

```bash
mainsequence project sync -m "Add vendor prices schedule"
mainsequence project images list
mainsequence project images create
mainsequence project schedule_batch_jobs scheduled_jobs.yaml
mainsequence project jobs list
mainsequence project jobs runs list <JOB_ID>
mainsequence project jobs runs logs <JOB_RUN_ID> --max-wait-seconds 900
```

The response should explain that the job reads a platform-managed Artifact rather than depending on a fragile local path on one machine.
