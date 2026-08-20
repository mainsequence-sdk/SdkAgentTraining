# Target Source and Snapshot Workflow

Targets are acquired from a configured GitHub HTTPS repository and a tag or full
commit. Installed Python distributions are not the source of truth.

For each target:

1. declare the repository URL, ref, exact global-context files, and exact unit
   roots or explicit entries;
2. resolve a tag to one 40-character commit;
3. safely acquire only that revision with no submodules/LFS unless explicitly
   enabled;
4. reject links, traversal, collisions, missing required files, and count/id
   assertion failures;
5. publish the extracted snapshot outside Git by content hash;
6. generate a compact lock containing upstream source path, normalized snapshot
   path, size, and hash for every file/unit;
7. verify the external snapshot from the lock without network access.

Example:

```bash
ms-agent-eval target resolve TARGET_ID --workspace path/to/workspace.yaml
ms-agent-eval target snapshot TARGET_ID \
  --workspace path/to/workspace.yaml \
  --data-root "$MS_AGENT_EVAL_DATA_ROOT"
```

Hidden skill roots such as `.agents/skills` work only when written in the target
configuration. The resolver never guesses them. Multiple roots require stable
logical prefixes and reject duplicate unit ids.

The Main Sequence v4.4.5 workspace records GitHub tag `v4.4.5`, resolved commit
`3b5a20a344cec0c960351dc3c601d32a66a8b46e`, global context
`agent_scaffold/AGENTS.md`, and unit root `agent_scaffold/skills`. That is one
target configuration, not a framework convention.
