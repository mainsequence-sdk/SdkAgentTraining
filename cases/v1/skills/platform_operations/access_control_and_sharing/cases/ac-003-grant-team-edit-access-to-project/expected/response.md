The answer should use the project team-sharing command and then verify the edit path.

Strong commands:

```bash
mainsequence project add_team_to_edit 42 9
mainsequence project can_edit 42
```

Weak answers should be rejected if they:

- use `add_to_edit` instead of `add_team_to_edit`
- use `view` instead of `edit`
- omit the verification command
