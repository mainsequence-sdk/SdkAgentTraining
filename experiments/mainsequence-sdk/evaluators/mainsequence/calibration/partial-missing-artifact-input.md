Commit a version-controlled `scheduled_jobs.yaml` with a `jobs:` entry using
`execution_path`, a weekday `crontab`, and a pinned `related_image_id`. Use
`mainsequence project schedule_batch_jobs scheduled_jobs.yaml`; do not use
`--strict` unless this is the full desired state. Verify with `mainsequence
project jobs list`, `mainsequence project jobs runs list <JOB_ID>`, and
`mainsequence project jobs runs logs <RUN_ID>`.

For the vendor CSV, mount a local file path from the operator laptop. An
Artifact can be created later for the output report.
