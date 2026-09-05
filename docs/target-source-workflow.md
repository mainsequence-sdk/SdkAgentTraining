# Target Source and Snapshot Workflow

The target is configured directly in `workspace.yaml`:

```yaml
evaluation:
  repository:
    url: https://github.com/example/project
    ref: v1.2.3
  instructions:
    global:
      - AGENTS.md
    skills:
      directory: .agents/skills
```

An exact file list is the only alternative:

```yaml
skills:
  files:
    - .agents/skills/one/SKILL.md
    - .agents/skills/two/SKILL.md
```

`validate`, `inspect`, `cases build`, and `run` automatically:

1. resolve an authored tag to one full commit;
2. materialize only that revision without submodules or Git LFS;
3. read every configured global file;
4. recursively discover `SKILL.md` under the configured directory, or use the
   exact file list, and catalog those instructions separately;
5. reject links, traversal, missing files, empty discovery, and duplicate skill
   ids;
6. publish the immutable repository bytes under the external data root so the
   case builder can ground source paths without another source registry;
7. generate a lock with requested ref, resolved commit, repository path,
   normalized snapshot path, size, and content hash for every file;
8. reuse and verify the snapshot without network on later runs.

There is no target registry, snapshot registry, compatibility map, authored
count assertion, locator filename, or fallback path probing. A hidden directory
such as `.agents/skills` works only when the manifest explicitly selects it.

The default external location is `~/ms_agent_eval/<workspace-id>/snapshots`.
Set `workspace.data_root` to another path outside the Git workspace when needed.
