from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml

from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.workspace import (
    WorkspaceConfiguration,
    WorkspaceRepository,
    resolve_role_models,
)
from ms_agent_eval.core import planning
from ms_agent_eval.core.planning import acquire_snapshot, inspect_workspace
from ms_agent_eval.core.snapshots import ExternalSnapshotStore, SnapshotBuilder
from ms_agent_eval.core.sources import ResolvedSource

from .helpers import create_checkout, create_snapshot, create_workspace, workspace_payload


def test_skills_require_exactly_one_selection_form() -> None:
    both = workspace_payload(skills={"directory": "skills", "files": ["skills/a/SKILL.md"]})
    neither = workspace_payload(skills={})
    with pytest.raises(ConfigurationError, match="exactly one"):
        WorkspaceConfiguration.from_mapping(both)
    with pytest.raises(ConfigurationError, match="exactly one"):
        WorkspaceConfiguration.from_mapping(neither)


def test_explicit_skill_files_are_the_only_directory_alternative() -> None:
    workspace = WorkspaceConfiguration.from_mapping(
        workspace_payload(
            skills={
                "files": [
                    "skills/alpha/SKILL.md",
                    "skills/beta/SKILL.md",
                ]
            }
        )
    )
    assert workspace.evaluation.instructions.skills.directory is None
    assert workspace.evaluation.instructions.skills.files == (
        "skills/alpha/SKILL.md",
        "skills/beta/SKILL.md",
    )


def test_resolved_llm_roles_must_be_distinct() -> None:
    workspace = WorkspaceConfiguration.from_mapping(workspace_payload())
    environment = {
        "BUILDER_MODEL": "builder",
        "SOLVER_MODEL": "solver",
        "JUDGE_MODEL": "judge",
        "OLLAMA_ENDPOINT": "http://localhost:11434",
    }
    models = resolve_role_models(workspace, "baseline", environment)
    assert set(models) == {"case_builder", "solver", "judge"}
    environment["JUDGE_MODEL"] = "solver"
    with pytest.raises(ConfigurationError, match="three distinct"):
        resolve_role_models(workspace, "baseline", environment)


def test_role_reuse_is_rejected_even_when_endpoints_differ() -> None:
    payload = workspace_payload()
    payload["evaluation"]["judge"]["model"]["endpoint_env"] = "JUDGE_ENDPOINT"  # type: ignore[index]
    workspace = WorkspaceConfiguration.from_mapping(payload)
    environment = {
        "BUILDER_MODEL": "builder",
        "SOLVER_MODEL": "shared",
        "JUDGE_MODEL": "shared",
        "OLLAMA_ENDPOINT": "http://localhost:11434",
        "JUDGE_ENDPOINT": "http://remote.example:11434",
    }
    with pytest.raises(ConfigurationError, match="three distinct"):
        resolve_role_models(workspace, "baseline", environment)


def test_noncanonical_solver_signature_is_rejected() -> None:
    payload = workspace_payload()
    payload["experiments"]["baseline"]["solver"]["dspy"]["signature"]["inputs"][  # type: ignore[index]
        "rubric"
    ] = "str"
    with pytest.raises(ConfigurationError, match="canonical solver"):
        WorkspaceConfiguration.from_mapping(payload)


def test_unknown_legacy_workspace_surface_is_rejected() -> None:
    payload = workspace_payload()
    payload["targets"] = {"legacy": "not-supported"}
    with pytest.raises(ConfigurationError, match="unknown fields"):
        WorkspaceConfiguration.from_mapping(payload)


def test_default_data_root_is_external_and_workspace_specific(tmp_path: Path) -> None:
    manifest = tmp_path / "workspace.yaml"
    manifest.write_text(yaml.safe_dump(workspace_payload(), sort_keys=False), encoding="utf-8")
    repository = WorkspaceRepository.from_file(manifest)
    assert repository.data_root == Path.home() / "ms_agent_eval" / "synthetic-evaluation"


def test_bootstrap_inspection_reports_readiness_without_cases_or_models(
    tmp_path: Path,
) -> None:
    repository = create_workspace(tmp_path / "workspace")
    snapshot, snapshot_directory = create_snapshot(
        repository,
        create_checkout(tmp_path),
        tmp_path / "external",
    )
    (repository.cases_root / "splits.yaml").write_text(
        "schema_version: 2\ngroups: {}\n", encoding="utf-8"
    )
    (repository.calibration_root / "manifest.yaml").write_text(
        "schema_version: 2\nfixtures: []\n", encoding="utf-8"
    )

    result = inspect_workspace(
        repository,
        environment={},
        snapshot=snapshot,
        snapshot_directory=snapshot_directory,
    )

    assert result["status"] == "incomplete"
    assert result["ready_for_scored_run"] is False
    assert result["cases"]["count"] == 0  # type: ignore[index]
    assert result["judge"]["calibration"]["status"] == "incomplete"  # type: ignore[index]
    assert result["experiments"]["baseline"]["lock_hash"] is None  # type: ignore[index]


def test_snapshot_cache_is_keyed_by_canonical_url_and_resolved_tag_commit(
    tmp_path: Path, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    root = tmp_path / "workspace"
    root.mkdir()
    external = tmp_path / "external"
    payload = workspace_payload()
    payload["workspace"]["data_root"] = external.as_posix()  # type: ignore[index]
    manifest = root / "workspace.yaml"
    manifest.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    repository = WorkspaceRepository.from_file(manifest)
    checkout = create_checkout(tmp_path)
    source = repository.target_specification().source
    resolved = [
        ResolvedSource(
            source.repository_url,
            source.repository_url + ".git",
            source.ref,
            "a" * 40,
        )
    ]
    store = ExternalSnapshotStore(external, workspace_root=repository.root)
    first = SnapshotBuilder(None, store).create_from_checkout(  # type: ignore[arg-type]
        repository.target_specification(), resolved[0], checkout
    )

    class Provider:
        def resolve(self, configured):  # type: ignore[no-untyped-def]
            assert configured == source
            return resolved[0]

        def materialize(self, configured, destination):  # type: ignore[no-untyped-def]
            assert configured == resolved[0]
            shutil.copytree(checkout, destination)

    monkeypatch.setattr(planning, "GitHubSourceProvider", Provider)
    cached, _ = acquire_snapshot(repository)
    assert cached == first

    resolved[0] = ResolvedSource(
        source.repository_url,
        source.repository_url + ".git",
        source.ref,
        "b" * 40,
    )
    moved, _ = acquire_snapshot(repository)
    assert moved.resolved_commit == "b" * 40
    assert moved.content_hash != first.content_hash
