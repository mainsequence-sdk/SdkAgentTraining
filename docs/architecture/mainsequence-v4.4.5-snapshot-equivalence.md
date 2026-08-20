# Main Sequence v4.4.5 Snapshot Equivalence Audit

Date: 2026-08-19
Result: **byte-equivalent — 21/21 configured instruction files match**

## Immutable Source Identity

| Field | Value |
|---|---|
| Repository | `https://github.com/mainsequence-sdk/mainsequence-sdk.git` |
| Requested ref | tag `v4.4.5` |
| Resolved commit | `3b5a20a344cec0c960351dc3c601d32a66a8b46e` |
| Target specification hash | `sha256:5b17c2d1956d5ad4cdc41f5b59a467ace6e35728f35657f7c78afa034bf9fbf3` |
| Extraction configuration hash | `sha256:a5e9032f738b9f8ea61145cdac7d450ad7f5a1dc1e7d771ff30c864d8e805016` |
| Inventory hash | `sha256:c1fb9df2c77737fcaddb216ae5ebba6af9b984d4c963679c41216e13c659d441` |
| Snapshot lock hash | `sha256:4639106bfd6c81d07ba0c1262dd0ae9f203c9b27b7b2599349ae29b42879a962` |
| Global context files | 1 |
| Instruction units | 20 |

The public tag was resolved by Git, including annotated-tag peeling behavior,
then fetched by its exact commit. The snapshot retains the complete repository
externally so the builder can ground cases in supporting code. The selected
instruction subset is still locked explicitly as:

```text
agent_scaffold/AGENTS.md
agent_scaffold/skills/**/SKILL.md
```

The fetched checkout, full snapshot, and generated lock are stored under the
external data root and are not added to Git. `workspace.yaml` is the only source
configuration committed in the experiment workspace.

## Byte Comparison

The upstream byte stream at
`agent_scaffold/skills/<unit-id>/SKILL.md` was compared with the former
schema-v0 normalized copy. That redundant copy was removed after the compact
snapshot lock captured every source path, size, and content hash.

| Unit id | SHA-256 | Result |
|---|---|---|
| `a2a_communication` | `c0cbc55dc070e3178706a383cf16e340f634346e4d0cc54ac7157cc711c375d1` | exact |
| `application_surfaces/api_surfaces` | `e9d93fe73cad371a01fe0a1e4e3df884f982ba07fd128ba6fdc9f741f6bc627d` | exact |
| `command_center/adapter_from_api` | `26bfa63204cf4c806cc0778fd5dcf4a60e3278fcea0f3c296237711684d94c82` | exact |
| `command_center/api_mock_prototyping` | `ad534f60454311b16392b7899664df5efc8b54a6f391fe0891d3e7c68d66af9a` | exact |
| `command_center/app_components` | `564af647aa0264183687b6c8fadbc9651f47fee67803a13578590bcba9facf2b` | exact |
| `command_center/connections` | `d9055011e7a566b5b1edb9646bb4b035ba29be72b359c1d0deb37b1b9f0d8caa` | exact |
| `command_center/workspace_analysis` | `44a777dcfabe281cde58d3662d59f440f49debf4aa8b146a23a10f1faab1ec3d` | exact |
| `command_center/workspace_builder` | `54996f38ca89ba4bc4339b462ce5c383b24a1bd9046eedbec031603ca4273e93` | exact |
| `command_center/workspace_design` | `fb6056be28185f7acbec1b66d64a85171a0c5f32ea34c3f95235ba8d66d631b1` | exact |
| `dashboards/streamlit` | `b938679c46d9efb8de009b49ba701741e9e8967d3a10c67c572f3d94d6535426` | exact |
| `data_access/exploration` | `b0c124e5b740a8a9d8fcb17ec727f2f5e7a2a4fbe835b4cd5849e210b1aa6a72` | exact |
| `data_publishing/data_nodes` | `b15cb3bc19e133ca3c0f929b2d963b9c75446a12a55174c93e8c497c89dbbe5b` | exact |
| `data_publishing/meta_table_migrations` | `a957a34089e0aa842de522e1788fd809071501367a07cec2a6b5b631eeedbb30` | exact |
| `data_publishing/meta_tables` | `f47de7e6295a25bb4e8041a00872d10cf1e82a1ae28137fae600cdf07998bf01` | exact |
| `maintenance/bug_auditor` | `eb828a5990ef19436287659feeef1722505efca8e63c8567a1461283bb6bb3d9` | exact |
| `ms-markets` | `ed3dbec7a93ffdc3f3d2dc8f332b2cd6f7de59ac1baa13a9bfced7ae966ace77` | exact |
| `platform_operations/access_control_and_sharing` | `a14a0eab905f52a319daf68dad5fd3124a8a5a01ac7cd6b9c80af209013488e5` | exact |
| `platform_operations/orchestration_and_releases` | `f1b48fb078d18df17add8d38f0c4a6c2279751a11792c730ac77384b82097200` | exact |
| `project_builder` | `082e8a6b23bc5bd3ad17b5625ba73920c1bc4dca14ddef0f8eb0f754042e2ebe` | exact |
| `project_to_agent` | `81a288c08ae84a91146a6900910442bd97b255a8585ece6be0056b853b2bf380` | exact |

The global context `AGENTS.md` also matches exactly at
`sha256:6b0608087855d70bd7c086550c1f27cd5659e0dd32fa162d720363e78f94dbdc`.

## Classification

No discrepancy exists to classify:

- packaging transformation: none detected;
- local snapshot drift: none detected;
- incorrect extraction configuration: none detected.

Therefore the removed schema-v0 instruction snapshot was a byte-faithful
namespace transformation of the configured public GitHub source at the locked
commit. Current experiments resolve the upstream source and generated lock into
external content-addressed storage; neither repository copies nor snapshot
locks are committed under `experiments/`.
