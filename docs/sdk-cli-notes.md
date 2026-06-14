# SDK CLI Notes

These notes describe the installed public `mainsequence` package surfaces that matter for this training repo.

## Relevant Surfaces

The library exposes `agent_scaffold` as an installed package bundle, and the CLI exposes related bundle operations through:

- `mainsequence skills list`
- `mainsequence skills path`
- `mainsequence project update_agent_skills`

## Important Implementation Detail

- `mainsequence skills list` and `mainsequence skills path` resolve installed `agent_scaffold` skills from the installed package bundle
- `mainsequence project update_agent_skills` copies the installed bundle into `.agents/skills/` for a target project

## Training Script Rule

For this repo, the population script should not take arguments.

It should:

1. read the installed `mainsequence` version
2. import the installed `agent_scaffold` package
3. copy the installed skill bundle into `sdk/<version>/`
4. create or preserve `sdk/<version>/source-of-truth.yaml`
5. refresh `sdk/<version>/case-map.yaml`

## Source-Of-Truth Rule

The installed package version is not enough to make an evaluation auditable.
Each `sdk/<version>/` snapshot must include `source-of-truth.yaml` with the
public git repository, tag/ref, and resolved commit when verified.

For `mainsequence==4.4.5`, the verified source ref is:

```yaml
repository: https://github.com/mainsequence-sdk/mainsequence-sdk
ref: refs/tags/v4.4.5
commit: 3b5a20a344cec0c960351dc3c601d32a66a8b46e
```

The authored case bank should stay under `cases/<case-set-version>/...` and should not be recopied for every SDK version.
