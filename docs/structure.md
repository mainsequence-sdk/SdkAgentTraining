# Repository Structure

## Library source

`src/ms_agent_eval/` is the single installable Python library:

```text
core/                    neutral schemas, planning, storage, execution, and plugin loading
programs/raw/            exact prompt rendering
programs/dspy/           optional DSPy programs and governed optimization
providers/ollama/        Ollama transport and bindings
```

The wheel contains no target-specific evaluator, evaluated-repository code, or
MainSequence dependency. Trusted evaluator code is selected explicitly from an
experiment workspace; a composite hash of its profile, module, and calibration
tree is included in every experiment lock.

## Experiment workspaces

Each directory under `experiments/` is self-contained:

```text
workspace.yaml
.env.example              committed template for machine-local external storage
targets/                 GitHub URL/ref and exact instruction locators
snapshots/               compact immutable source locks
sources/                 authored source notes; never repository clones
suites/
  <version>/
    suite.yaml            case index
    split.json            grouped train/development/test/challenge assignments
    units/<unit>/cases/   authored cases, expected answers, and rubrics
compatibility/            exact snapshot/suite/bundle/unit mappings
programs/                 raw or DSPy program specifications
providers/                credential-free provider profiles
runtimes/                 response-only or digest-pinned Docker profiles
evaluators/
  <evaluator>/
    evaluator.yaml        trusted module, factory, and calibration configuration
    plugin.py             target-specific evaluator implementation
    calibration/          positive, negative, and adversarial fixtures
optimizers/               DSPy optimizer profiles and hard budgets
storage/                  environment-rooted external backends
plans/                    benchmark or optimization matrices
```

An instruction root is exactly what the target declares. `.agents/skills`,
`agent_scaffold/skills`, explicit files, and multiple prefixed roots are all
supported; none is probed implicitly.

## External data plane

`MS_AGENT_EVAL_DATA_ROOT` points outside the Git workspace and owns all generated
state:

```text
blobs/sha256/             immutable content-addressed bytes
manifests/                locks, results, evaluations, reports, and legacy indexes
metadata/                 SQLite lifecycle and artifact-reference metadata
snapshots/                safely extracted immutable repository snapshots
tmp/                      atomic-write staging
```

Each target executes in its own Docker mount and dependency environment. Trusted
evaluators consume read-only evidence; evaluated repository code is never
imported into the host process.

## Repository root

```text
.agents/                  repository-local authoring workflows
src/                      the installable generic library
experiments/              committed workspaces and authored suites
tests/                    generic tests and narrow regression fixtures
docs/                     architecture and implementation records
```

There are no root-level cases, snapshots, runtime profiles, runs, reports,
packages, SDK copies, or spike environments.
