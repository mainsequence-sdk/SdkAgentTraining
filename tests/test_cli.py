from __future__ import annotations

import json
from pathlib import Path

from ms_agent_eval.core.cli import main
from ms_agent_eval.core import cli
from ms_agent_eval.core.planning import inspect_workspace as inspect_workspace_real
from ms_agent_eval.core.workspace import WorkspaceRepository


def test_init_creates_one_manifest_and_external_default(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = tmp_path / "workspace.yaml"
    result = main(
        [
            "init",
            "--id",
            "example-evaluation",
            "--repo",
            "https://github.com/example/repository",
            "--ref",
            "v1.0.0",
            "--global-instructions",
            "AGENTS.md",
            "--skills-directory",
            "skills",
            "--cases",
            "cases",
            "--workspace",
            str(workspace),
        ]
    )
    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["data_root"].endswith("ms_agent_eval/example-evaluation")
    repository = WorkspaceRepository.from_file(workspace)
    assert repository.workspace.schema_version == 2
    assert set(repository.workspace.experiments) == {"baseline", "optimize-few-shot"}


def test_validate_serializes_bootstrap_report(tmp_path: Path, capsys, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from .helpers import create_checkout, create_snapshot, create_workspace

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
    monkeypatch.setattr(
        cli,
        "inspect_workspace",
        lambda repository, environment: inspect_workspace_real(
            repository,
            environment={},
            snapshot=snapshot,
            snapshot_directory=snapshot_directory,
        ),
    )

    result = main(["validate", "--workspace", str(repository.workspace_file)])

    assert result == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "incomplete"
    assert payload["case_builder"]["model"]["status"] == "unresolved"
