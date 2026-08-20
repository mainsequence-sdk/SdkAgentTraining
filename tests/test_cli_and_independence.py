from __future__ import annotations

import json
import shutil
from pathlib import Path

from ms_agent_eval.core.cli import main


PACKAGE_ROOT = Path(__file__).parents[1]
FIXTURE = PACKAGE_ROOT / "tests" / "fixtures" / "workspace" / "workspace.yaml"


def test_validate_cli_emits_machine_readable_summary(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["config", "validate", "--workspace", str(FIXTURE)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "valid"
    assert payload["workspace"] == "synthetic-workspace"
    assert payload["documents"]["targets"] == 2


def test_evaluator_cli_loads_only_the_workspace_profile(capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = PACKAGE_ROOT / "experiments/mainsequence-sdk/workspace.yaml"
    assert (
        main(
            [
                "evaluator",
                "validate",
                "mainsequence-rules-v1",
                "--suite",
                "mainsequence-agent-skills-v2",
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "valid"
    assert payload["case_count"] == 74
    assert not (
        PACKAGE_ROOT
        / "experiments/mainsequence-sdk/evaluators/mainsequence/__pycache__"
    ).exists()


def test_evaluator_score_cli_runs_a_complete_offline_evaluation(capsys) -> None:  # type: ignore[no-untyped-def]
    workspace = PACKAGE_ROOT / "experiments/mainsequence-sdk/workspace.yaml"
    response = (
        PACKAGE_ROOT
        / "experiments/mainsequence-sdk/evaluators/mainsequence/calibration/ideal.md"
    )
    assert (
        main(
            [
                "evaluator",
                "score",
                "mainsequence-rules-v1",
                "--suite",
                "mainsequence-agent-skills-v2",
                "--case",
                "or-001-recurring-artifact-job",
                "--response",
                str(response),
                "--workspace",
                str(workspace),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "evaluated"
    assert payload["passed"] is True
    assert payload["score"] == 1.0


def test_plan_cli_writes_lock_atomically(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    output = tmp_path / "locks" / "two-targets.lock.json"
    assert (
        main(
            [
                "experiment",
                "plan",
                "two-targets",
                "--workspace",
                str(FIXTURE),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    stdout_payload = json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text(encoding="utf-8")) == stdout_payload
    assert len(stdout_payload["jobs"]) == 2


def test_create_cli_persists_run_only_below_external_root(
    tmp_path: Path, capsys
) -> None:  # type: ignore[no-untyped-def]
    data_root = tmp_path / "external"
    assert (
        main(
            [
                "experiment",
                "create",
                "two-targets",
                "--workspace",
                str(FIXTURE),
                "--data-root",
                str(data_root),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["run"]["id"].startswith("run-")
    assert (data_root / "metadata" / "ms-agent-eval.sqlite").is_file()
    manifest = data_root / payload["experiment_lock"]["relative_path"]
    assert manifest.is_file()


def test_create_cli_loads_data_root_from_workspace_dotenv(
    tmp_path: Path, capsys, monkeypatch
) -> None:  # type: ignore[no-untyped-def]
    workspace_root = tmp_path / "workspace"
    shutil.copytree(FIXTURE.parent, workspace_root)
    data_root = tmp_path / "external-from-dotenv"
    (workspace_root / ".env").write_text(
        f"MS_AGENT_EVAL_DATA_ROOT={data_root}\n", encoding="utf-8"
    )
    monkeypatch.delenv("MS_AGENT_EVAL_DATA_ROOT", raising=False)

    assert (
        main(
            [
                "experiment",
                "create",
                "two-targets",
                "--workspace",
                str(workspace_root / "workspace.yaml"),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert (data_root / "metadata/ms-agent-eval.sqlite").is_file()
    assert (data_root / payload["experiment_lock"]["relative_path"]).is_file()


def test_library_source_has_no_mainsequence_behavior_or_default() -> None:
    source_root = PACKAGE_ROOT / "src" / "ms_agent_eval"
    occurrences = []
    for path in source_root.rglob("*.py"):
        if "mainsequence" in path.read_text(encoding="utf-8").lower():
            occurrences.append(path.relative_to(source_root).as_posix())
    assert occurrences == []


def test_distribution_has_no_target_specific_entry_point_or_extension_tree() -> None:
    project = (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "ms-agent-eval-mainsequence" not in project
    assert not (PACKAGE_ROOT / "src/ms_agent_eval/extensions").exists()
