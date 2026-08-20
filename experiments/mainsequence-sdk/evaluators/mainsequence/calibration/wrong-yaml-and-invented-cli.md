Put the CSV file in the repository and create a one-off job. Use an image tagged
`latest`, then run `mainsequence project create_job --schedule weekday`. The
output can become an Artifact. There is no need for a repository-managed batch
file or run-log verification.
