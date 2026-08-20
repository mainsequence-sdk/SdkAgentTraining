# Framework and Experiment Conventions

## Ownership

- `src/ms_agent_eval` owns generic DSPy programs, source locking, case
  provenance, LLM judging, optimization governance, isolation, and reporting.
- `workspace.yaml` owns a repository URL/ref, exact instruction selection,
  three role models, case location, judge calibration, and experiments.
- Promoted case packages and human-labelled calibration inputs are versioned.
- External storage owns repository snapshots, builder drafts/calls, solver
  calls, judge calls, compiled state, evaluations, and reports.

An evaluated repository must never become a core dependency or default path.

## Repository identity

- Author an HTTPS GitHub URL plus a tag or full commit.
- Resolve tags to a full 40-character commit before model execution.
- Select global instruction files explicitly.
- Select skills with exactly one of `directory` or `files`.
- Reject links, traversal, duplicate ids, missing files, empty discovery, and
  source/snapshot hash mismatches.
- Counts and file hashes are generated lock evidence, not user assertions.

## Three LLM roles

- `case_builder`, `solver`, and `judge` must resolve to distinct provider/model
  identities.
- The builder sees locked instructions, source context, the coverage request,
  and summaries of existing cases. It never sees solver or judge evidence.
- The solver sees global context, skill context, and task only.
- The judge sees the rubric, expected response/artifacts, candidate response,
  task, and skill context.
- Every call records its role, rendered request, response, usage, latency,
  provider/model, parameters, and artifact identities externally.

## Cases and semantic judging

A promoted case contains:

```text
case.yaml
prompt.md
expected/response.md
expected/artifacts/       optional
rubric.yaml
```

`case.yaml` declares schema version, id, title, skill, leakage group, local file
references, immutable source paths, and builder provenance hashes. Direct edits
that change package identity invalidate provenance.

The configured DSPy judge LLM is the only semantic scorer. There are no Python
evaluator plugins, rule/checklist methods, evaluator status modes, keyword
judges, or manual-review scoring alternatives. Deterministic code may only:

- validate exact criterion and hard-failure ids;
- reject malformed scores outside `[0, 1]`;
- compute weighted totals;
- take the median criterion score across judge votes;
- apply majority voting to declared hard failures.

Judge calibration uses human-labelled strong, partial, incorrect,
contradictory, and adversarial candidate responses. Failure blocks every solver
call.

## Dataset governance

- Assign a leakage-resistant group, not each paraphrase, to a split.
- The builder proposes a group but cannot choose its split.
- Optimization can load train and development only.
- Judge calibration for optimization may reference train/development cases,
  never test/challenge cases.
- Publish state-only DSPy JSON with pickle and unsafe LM state disabled.
- Load untouched test data only after candidate publication.
- Never use test results to revise cases, prompts, demonstrations, or optimizer
  parameters.

## Runtime and secrets

- CPython 3.12+ is the baseline.
- `response_only` is valid when target code need not execute.
- Target code executes only in a digest-pinned Docker image with network none,
  a non-root user, read-only root filesystem, dropped capabilities, resource
  limits, bounded output, and automatic cleanup.
- Keep secrets in environment/provider facilities. Never commit them or include
  plaintext in locks and reports.

## Results

Every comparison locks repository commit/snapshot, case bytes and split,
builder identity, solver program/model, judge program/model, calibration corpus,
runtime, and compiled artifact. Reports must not aggregate records across a
changed correctness contract without labeling the difference.
