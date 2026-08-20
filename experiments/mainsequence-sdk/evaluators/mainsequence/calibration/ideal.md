Treat the weekday workflow as repository-managed configuration. Commit a
`scheduled_jobs.yaml` file so the team reviews and versions the schedule. The
vendor CSV is an input `Artifact`: upload it to the intended bucket/name and
resolve that managed file in `scripts/vendor_prices_launcher.py`, never through
a laptop path.

Use a pushed commit to build a project image, record its immutable image id, and
set `related_image_id` in the job. A representative reviewed file is:

```yaml
jobs:
  - name: vendor-prices-weekdays
    execution_path: scripts/vendor_prices_launcher.py
    mode: crontab
    crontab: "0 6 * * 1-5"
    related_image_id: "<PINNED_PROJECT_IMAGE_ID>"
    spot: false
```

Apply it with `mainsequence project schedule_batch_jobs scheduled_jobs.yaml`.
Do not add `--strict` in the shared environment unless this file is explicitly
approved as the complete desired job set, because strict sync may remove jobs.

Verify rather than stopping at creation: run `mainsequence project jobs list`,
trigger or wait for a run, inspect it with `mainsequence project jobs runs list
<JOB_ID>`, and read completion logs with `mainsequence project jobs runs logs
<JOB_RUN_ID> --max-wait-seconds 900`. Confirm the run resolved the intended
input Artifact and processed the expected CSV.
