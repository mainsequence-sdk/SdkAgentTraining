You are maintaining schema lifecycle for a Main Sequence project with many optional time-indexed storage tables.

Most deployments only need a small default model set. Some deployments need one selected bar frequency. A portfolio workflow also needs a source-dependent derived price storage table whose identity depends on a registered source table UID, the source cadence, the output frequency, and an interpolation rule.

The user asks:

"Design the migration workflow. I want to avoid cluttering every project with every optional table, but I also need one coherent migration history and a safe way to create the source-dependent table before the portfolio workflow runs."
