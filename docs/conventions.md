# Framework and Experiment Conventions

## Ownership

- Core owns neutral schemas, locks, lifecycle, storage, execution, evaluation
  contracts, and reporting.
- Program modules own rendering/compilation behavior.
- Provider modules own model transport and binding details.
- Experiment workspaces own targets, sources, co-located suite/split data,
  profiles, and target-specific trusted evaluators.
- External storage owns all generated/runtime evidence.

An evaluated library must never appear in core dependencies or defaults.

## Reproducible source identity

- Author a GitHub HTTPS URL plus tag or full commit.
- Resolve tags to a full commit before execution.
- Snapshot only exact configured paths.
- Reject symlinks, traversal, ambiguous unit ids, fallback-root probing, and
  source/snapshot hash mismatches.
- Identify every case through `(suite, version, bundle, unit, case)` and every
  run through locked target/snapshot/program/provider/runtime/evaluator
  identities.

## Cases and evaluators

A case directory contains `case.yaml`, `prompt.md`, `expected/`, and
`rubric.yaml`. Its evaluator block is mandatory:

```yaml
evaluator:
  name: example.correctness-v1
  method: rule-based-checklist
  status: active
```

Supported status/method pairs are:

- `active` / `rule-based-checklist`;
- `manual_review_required` / `human-review`;
- `not_evaluable` / `none`.

Registration uses the exact namespaced name. Every active evaluator must pass
positive, negative, and adversarial calibration. Missing coverage is a preflight
error, not a zero. Unscored generation has null score/pass fields.

Evaluator profiles point to trusted Python modules inside their workspace. The
generic wheel loads only the explicitly selected profile; target-specific code
must never live under `src/ms_agent_eval/`.

## Dataset governance

- Split by leakage-resistant group, never individual paraphrase alone.
- Optimization sees train and development only.
- Publish a content-addressed JSON compiled artifact before opening held-out
  test/challenge content.
- Report development and held-out results separately.
- Promote explicitly after held-out non-regression and anti-gaming checks.
- Never use test feedback to select a candidate or edit its prompt.

## Runtime and secrets

- Python 3.12 is the baseline.
- Execute repository code only in a digest-pinned Docker runtime.
- Default run network is `none`; build/network access must be separately scoped.
- Pass secrets by reference at runtime, never through committed YAML, locks,
  rendered-message evidence, or reports.
- Use a non-root user, read-only root filesystem, dropped capabilities, resource
  limits, bounded output, and automatic container removal.

## Results

Do not commit clones, extracted snapshots, prompts sent to models, responses,
logs, patches, evaluations, optimizer candidates, SQLite databases, or generated
reports. Store them under the selected external root and reference them by
content id.

Reports must show suite/version, target/commit/snapshot, bundle/unit,
program/engine/adapter/compiled artifact, split, provider/model/parameters, and
evaluator/version. Missing legacy identity is labeled `unresolved`.
