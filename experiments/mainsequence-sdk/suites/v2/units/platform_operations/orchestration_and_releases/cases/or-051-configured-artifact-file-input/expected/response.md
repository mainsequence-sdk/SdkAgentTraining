The answer should model the CSV as a platform-managed operational file.

Expected decisions:

- Use `Artifact` as the operational file primitive.
- Do not depend on local paths such as `/tmp/input.csv` or desktop downloads.
- Store only stable artifact identity in workflow configuration, such as bucket name and artifact name.
- Retrieve the file at execution time through SDK lookup, for example by bucket name and artifact name.
- Treat the artifact content as the CSV input stream for parsing.
- Keep file transport separate from downstream normalization into DataNodes, MetaTables, or other persisted outputs.
- If the workflow is scheduled or shared, run it through a job pinned to a project image rather than a laptop command.
- If the bucket or artifact needs team access, route that access decision to the access-control skill and verify the real bucket/artifact boundary.
- Verify that the artifact exists, the configured bucket/name resolves the intended file, the job environment can access it, the run logs show the artifact was loaded, and downstream row counts or output checks match expectations.

Important non-goals:

- Do not force a raw file into a DataNode before the operational file-transfer problem is solved.
- Do not store raw file bytes or local path strings in a Constant.
- Do not claim success from code review alone; verify artifact lookup and job execution behavior.
- Do not use `--strict` batch scheduling unless the scheduled jobs file is the full desired job state.
