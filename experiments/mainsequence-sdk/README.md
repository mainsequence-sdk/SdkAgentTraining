# MainSequence SDK Evaluation Workspace

This is the complete version-controlled template for evaluating the public
MainSequence SDK at tag `v4.4.5`. It contains configuration and authored
evaluation inputs only. Repository snapshots, DSPy calls, drafts, runs, and
compiled programs go to `~/ms_agent_eval/mainsequence-sdk-evaluation`.

## Part A — evaluation target

`workspace.yaml` points to:

- `https://github.com/mainsequence-sdk/mainsequence-sdk` at `v4.4.5`;
- global instructions at `agent_scaffold/AGENTS.md`;
- every recursively discovered `agent_scaffold/skills/**/SKILL.md`;
- promoted cases under `cases/`;
- the DSPy case-builder and DSPy rubric-judge contracts.

The case bank starts empty by design. Only a real observed builder call followed
by explicit promotion may create a schema-v2 case; no legacy case is retained
and no builder provenance is fabricated.

## Part B — experiments

The same manifest defines:

- `baseline`, which evaluates the typed DSPy solver against every promoted
  case;
- `optimize-few-shot`, which compiles `LabeledFewShot` using train cases,
  measures development cases, publishes state-only JSON, and only then scores
  the untouched test split.

The builder, solver, and judge must be three different provider/model names.
They may share one Ollama endpoint.

## Bootstrap and run

From the repository root:

```bash
cp experiments/mainsequence-sdk/.env.example \
  experiments/mainsequence-sdk/.env
```

Replace all three placeholder model names in `.env` with installed, distinct
Ollama models. Then:

```bash
uv run ms-agent-eval validate \
  --workspace experiments/mainsequence-sdk/workspace.yaml

uv run ms-agent-eval cases build \
  --workspace experiments/mainsequence-sdk/workspace.yaml \
  --coverage "Create grounded cases across every discovered MainSequence skill"

uv run ms-agent-eval cases inspect-drafts \
  --workspace experiments/mainsequence-sdk/workspace.yaml

uv run ms-agent-eval cases promote \
  --workspace experiments/mainsequence-sdk/workspace.yaml \
  --draft DRAFT_ID
```

Add human-labelled `strong`, `partial`, `incorrect`, `contradictory`, and
`adversarial` responses under `judge-calibration/`, each referencing a promoted
train/development case. Validate until `ready_for_scored_run` is `true`, then:

```bash
uv run ms-agent-eval inspect \
  --workspace experiments/mainsequence-sdk/workspace.yaml
uv run ms-agent-eval run baseline \
  --workspace experiments/mainsequence-sdk/workspace.yaml
uv run ms-agent-eval run optimize-few-shot \
  --workspace experiments/mainsequence-sdk/workspace.yaml
```

`validate` and `inspect` make no LLM requests. Before promotion they report the
empty case bank and calibration corpus as explicit blockers. `run` remains
strict and cannot start the solver until source, builder provenance, splits,
three model identities, and judge calibration are complete.

## Workspace-specific documentation

- [DataNode evaluation specification](docs/datanode-evaluation-spec.md)
- [SimpleTable evaluation specification](docs/simpletable-evaluation-spec.md)
- [SimpleTableUpdater evaluation specification](docs/simpletable-updater-evaluation-spec.md)
- [v4.4.5 snapshot equivalence audit](docs/v4.4.5-snapshot-equivalence.md)
