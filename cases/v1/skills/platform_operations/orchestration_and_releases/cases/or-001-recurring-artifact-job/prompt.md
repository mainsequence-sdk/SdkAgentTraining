You are helping operationalize a Main Sequence project.

The project has a launcher script at `scripts/vendor_prices_launcher.py`. Every weekday at 06:00 UTC, a vendor drops a CSV file that should be uploaded as a platform-managed file and then processed by the project workflow.

The user asks:

"Set this up so the workflow is reproducible and team-managed. I do not want an ad hoc shell command that only lives on one laptop. Explain exactly how you would structure it, what file should exist in the repo, how the job should be scheduled, how the file input should be handled, and how you would verify that the setup actually works."

Answer as the orchestration and releases skill owner.

Your answer should:

- choose the correct orchestration approach
- mention the role of `Artifact`
- show a concrete `scheduled_jobs.yaml` example
- explain the image strategy
- mention the CLI commands used to apply and verify the setup
- explain whether `--strict` should be used here
