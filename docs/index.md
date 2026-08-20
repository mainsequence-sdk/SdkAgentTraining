# MS Agent Eval Documentation

MS Agent Eval is a Python 3.12+ DSPy framework with three distinct LLM roles:
case builder, solver, and LLM judge.

## Start here

1. [Getting started](getting-started.md) — complete repository-to-result flow.
2. [Repository structure](structure.md) — what is versioned and what remains external.
3. [Framework conventions](conventions.md) — identities, provenance, judging, and splits.
4. [Ollama workflow](ollama-workflow.md) — configure the three local model roles.
5. [Target source workflow](target-source-workflow.md) — immutable repository snapshots.
6. [MainSequence template](../experiments/mainsequence-sdk/README.md) — concrete bootstrap-to-run example.

## Architecture

- [Three-LLM DSPy workspace](implementation_tasks/017-dspy-only-workspace-ux.md)
- [MainSequence v4.4.5 snapshot equivalence](architecture/mainsequence-v4.4.5-snapshot-equivalence.md)

Numbered files under [implementation_tasks](implementation_tasks/) are the
historical implementation record. When an older task conflicts with task 017,
task 017 is authoritative.

Generated snapshots, drafts, model calls, results, compiled programs, and
reports belong under `~/ms_agent_eval/<workspace-id>` or the explicit external
`workspace.data_root`, never in this repository.
