You are operationalizing a Main Sequence workflow that consumes a CSV file supplied by another team.

The workflow code should run the same way from a scheduled job, a one-off job, or a teammate's project checkout. The input file must not be referenced as `/tmp/input.csv`, a desktop download, or any other laptop-specific path. The workflow configuration can store a bucket name and an artifact name.

The user asks:

"Explain how to model this CSV input operationally, how the job should find the file at runtime, what belongs in configuration, and how you would verify the setup before relying on it."
