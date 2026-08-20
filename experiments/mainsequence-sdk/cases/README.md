# Promoted MainSequence Cases

Only schema-v2 cases explicitly promoted from the configured DSPy case-builder
belong here. Builder requests, responses, and rejected drafts remain under
`~/ms_agent_eval/mainsequence-sdk-evaluation/case-drafts`.

This directory intentionally starts with only `splits.yaml`. Configure three
real model identities, run `cases build`, inspect the external drafts, and
promote only accepted packages. The removed pre-task-017 suites are not kept as
fallbacks, and their files are never relabelled with invented provenance.
