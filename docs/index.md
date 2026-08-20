# MS Agent Eval Documentation

MS Agent Eval is a Python 3.12+ framework for evaluating and optimizing prompts
and instruction bundles from arbitrary GitHub repositories. Evaluated projects
are configuration and isolated runtime inputs; they are not library
dependencies.

## Start here

1. [Getting started](getting-started.md) — run a complete offline response
   evaluation in a few commands.
2. [Repository structure](structure.md) — understand library, experiment, and
   external-data ownership.
3. [Framework conventions](conventions.md) — source identity, dataset splits,
   evaluator trust, Docker, and result rules.

## Operating workflows

- [Target source workflow](target-source-workflow.md) — resolve a GitHub tag or
  commit and build an immutable external snapshot.
- [Ollama workflow](ollama-workflow.md) — configure local model execution.

## Evaluation specifications

- [DataNode evaluation](datanode-evaluation-spec.md)
- [SimpleTable evaluation](simpletable-evaluation-spec.md)
- [SimpleTableUpdater evaluation](simpletable-updater-evaluation-spec.md)

## Architecture and implementation

- [DSPy feasibility report](architecture/dspy-feasibility-report.md)
- [MainSequence v4.4.5 snapshot equivalence](architecture/mainsequence-v4.4.5-snapshot-equivalence.md)
- [Canonical experiment workspace](implementation_tasks/016-canonical-experiment-workspace-layout.md)
- [Implementation task records](implementation_tasks/)

Generated snapshots, prompts sent to models, responses, evaluations, optimizer
artifacts, databases, and reports belong under the configured external data
root—not in this Git repository.
