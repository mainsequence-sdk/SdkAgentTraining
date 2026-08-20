from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from ms_agent_eval.core.errors import ConfigurationError, IntegrityError, ResolutionError
from ms_agent_eval.core.models import GitSource, SourceRef, SourceRefKind, TargetSpecification
from ms_agent_eval.core.snapshots import ExternalSnapshotStore, SnapshotBuilder
from ms_agent_eval.core.sources import GitHubSourceProvider, ResolvedSource


def _source(ref_type: str = "tag", value: str = "v1.0.0") -> GitSource:
    return GitSource.from_mapping(
        {
            "type": "github",
            "repository_url": "https://github.com/example/project",
            "ref": {"type": ref_type, "value": value},
        }
    )


def _target(*, exact_count: int = 1) -> TargetSpecification:
    return TargetSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "configured-hidden-root",
            "source": {
                "type": "github",
                "repository_url": "https://github.com/example/project",
                "ref": {"type": "tag", "value": "v1.0.0"},
            },
            "instruction_bundles": [
                {
                    "id": "agent-material",
                    "global_context": [
                        {"id": "root", "source_path": "AGENTS.md", "required": True}
                    ],
                    "units": {
                        "sources": [
                            {
                                "id": "hidden-skills",
                                "type": "directory",
                                "root": ".agents/skills",
                                "locator": {
                                    "filename": "SKILL.md",
                                    "recursive": True,
                                    "include": ["**/SKILL.md"],
                                    "exclude": [],
                                    "follow_symlinks": False,
                                },
                                "logical_id": {"prefix": "project"},
                                "assertions": {
                                    "exact_count": exact_count,
                                    "required_ids": ["project/coding"],
                                },
                            }
                        ]
                    },
                }
            ],
        }
    )


def _resolved() -> ResolvedSource:
    return ResolvedSource(
        repository_url_requested="https://github.com/example/project",
        repository_url_canonical="https://github.com/example/project.git",
        requested_ref=SourceRef(SourceRefKind.TAG, "v1.0.0"),
        resolved_commit="a" * 40,
    )


def test_annotated_tag_prefers_peeled_commit() -> None:
    calls = []

    def runner(arguments, cwd):  # type: ignore[no-untyped-def]
        calls.append((arguments, cwd))
        return (
            f"{'b' * 40}\trefs/tags/v1.0.0\n"
            f"{'a' * 40}\trefs/tags/v1.0.0^{{}}\n"
        )

    resolved = GitHubSourceProvider(runner).resolve(_source())
    assert resolved.resolved_commit == "a" * 40
    assert resolved.repository_url_canonical.endswith(".git")
    assert calls[0][0][0:2] == ["ls-remote", "--tags"]


@pytest.mark.parametrize("tag", ["--upload-pack=bad", "a..b", "a@{b", "a.lock"])
def test_unsafe_tag_is_rejected_before_git(tag: str) -> None:
    with pytest.raises(ConfigurationError, match="unsafe"):
        _source(value=tag)


def test_snapshot_uses_only_configured_hidden_root_and_verifies_offline(
    tmp_path: Path,
) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".agents" / "skills" / "coding").mkdir(parents=True)
    (checkout / "unconfigured" / "skills" / "ignored").mkdir(parents=True)
    (checkout / "AGENTS.md").write_text("# Context\n", encoding="utf-8")
    (checkout / ".agents" / "skills" / "coding" / "SKILL.md").write_text(
        "# Coding\n", encoding="utf-8"
    )
    (checkout / "unconfigured" / "skills" / "ignored" / "SKILL.md").write_text(
        "# Must not be selected\n", encoding="utf-8"
    )
    store = ExternalSnapshotStore(tmp_path / "external-data")
    builder = SnapshotBuilder(GitHubSourceProvider(), store)
    lock = builder.create_from_checkout(_target(), _resolved(), checkout)

    assert [(unit.unit_id, unit.source_path) for unit in lock.units] == [
        ("project/coding", ".agents/skills/coding/SKILL.md")
    ]
    assert all("unconfigured" not in item.source_path for item in lock.files)
    shutil.rmtree(checkout)
    store.verify(lock)


def test_snapshot_rejects_inventory_assertion_failure(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".agents" / "skills" / "coding").mkdir(parents=True)
    (checkout / "AGENTS.md").write_text("context", encoding="utf-8")
    (checkout / ".agents" / "skills" / "coding" / "SKILL.md").write_text(
        "coding", encoding="utf-8"
    )
    builder = SnapshotBuilder(
        GitHubSourceProvider(), ExternalSnapshotStore(tmp_path / "external-data")
    )
    with pytest.raises(ResolutionError, match="expected 2"):
        builder.create_from_checkout(_target(exact_count=2), _resolved(), checkout)


def test_multiple_roots_require_non_colliding_logical_ids(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / "docs").mkdir(parents=True)
    (checkout / "docs" / "first.md").write_text("first", encoding="utf-8")
    (checkout / "docs" / "second.md").write_text("second", encoding="utf-8")

    def target(prefixes: tuple[str, str]) -> TargetSpecification:
        sources = []
        for index, path in enumerate(("docs/first.md", "docs/second.md")):
            sources.append(
                {
                    "id": f"source-{index}",
                    "type": "explicit",
                    "entries": [{"id": "coding", "source_path": path}],
                    "logical_id": {"prefix": prefixes[index]},
                }
            )
        return TargetSpecification.from_mapping(
            {
                "schema_version": 1,
                "id": "multi-root",
                "source": {
                    "type": "github",
                    "repository_url": "https://github.com/example/project",
                    "ref": {"type": "tag", "value": "v1.0.0"},
                },
                "instruction_bundles": [
                    {"id": "agent-material", "units": {"sources": sources}}
                ],
            }
        )

    builder = SnapshotBuilder(
        GitHubSourceProvider(), ExternalSnapshotStore(tmp_path / "external-data")
    )
    with pytest.raises(ResolutionError, match="collision"):
        builder.create_from_checkout(target(("", "")), _resolved(), checkout)

    lock = builder.create_from_checkout(target(("core", "extension")), _resolved(), checkout)
    assert [unit.unit_id for unit in lock.units] == ["core/coding", "extension/coding"]


def test_snapshot_rejects_symlinked_instruction_file(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".agents" / "skills" / "coding").mkdir(parents=True)
    (checkout / "AGENTS.md").write_text("context", encoding="utf-8")
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    (checkout / ".agents" / "skills" / "coding" / "SKILL.md").symlink_to(outside)
    builder = SnapshotBuilder(
        GitHubSourceProvider(), ExternalSnapshotStore(tmp_path / "external-data")
    )
    with pytest.raises(ResolutionError, match="symlink"):
        builder.create_from_checkout(_target(), _resolved(), checkout)


def test_external_data_root_cannot_be_inside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ConfigurationError, match="outside"):
        ExternalSnapshotStore(workspace / "var", workspace_root=workspace)


def test_snapshot_verification_detects_content_tampering(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    (checkout / ".agents" / "skills" / "coding").mkdir(parents=True)
    (checkout / "AGENTS.md").write_text("context", encoding="utf-8")
    (checkout / ".agents" / "skills" / "coding" / "SKILL.md").write_text(
        "coding", encoding="utf-8"
    )
    store = ExternalSnapshotStore(tmp_path / "external-data")
    lock = SnapshotBuilder(GitHubSourceProvider(), store).create_from_checkout(
        _target(), _resolved(), checkout
    )
    path = store.directory(lock) / lock.files[0].snapshot_path
    path.write_text("tampered", encoding="utf-8")
    with pytest.raises(IntegrityError, match="hash mismatch"):
        store.verify(lock)
