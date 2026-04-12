# SDK CLI Notes

These notes describe the installed public `mainsequence` package surfaces that matter for this training repo.

## Relevant surfaces

The library exposes `agent_scaffold` as an installed package bundle, and the CLI also exposes it through:

- `mainsequence skills list`
- `mainsequence skills path`
- `mainsequence project update_agent_skills`

The documented CLI references are:

- `mainsequence skills list`
- `mainsequence skills path`
- `mainsequence project update_agent_skills`

## Important implementation detail

`mainsequence skills list` and `mainsequence skills path` resolve installed `agent_scaffold` skills from the installed package bundle.

`mainsequence project update_agent_skills` copies the installed bundle into `.agents/skills/` for a target project.

## Training script rule

For this repo, the population script should not take arguments.

It should:

1. read the installed `mainsequence` version
2. import the installed `agent_scaffold` package
3. copy the installed skill bundle into `cases/sdk/<version>/`

That keeps the corpus aligned with the actually installed library version.
