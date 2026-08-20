from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import shutil

import pytest

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.models import ExperimentLock
from ms_agent_eval.core.planning import lock_as_dict, plan_experiment


FIXTURE = Path(__file__).parent / "fixtures" / "workspace" / "workspace.yaml"


def test_all_fixture_documents_validate() -> None:
    repository = ConfigurationRepository.from_file(FIXTURE)
    assert repository.validate_all() == {
        "compatibility": 2,
        "evaluators": 1,
        "optimizers": 1,
        "plans": 1,
        "programs": 1,
        "providers": 1,
        "runtimes": 1,
        "snapshots": 2,
        "splits": 1,
        "storage": 1,
        "suites": 1,
        "targets": 2,
    }


def test_two_target_plan_is_deterministic_and_filters_snapshot_pairs() -> None:
    repository = ConfigurationRepository.from_file(FIXTURE)
    first = plan_experiment(repository, "two-targets")
    second = plan_experiment(repository, "two-targets")
    assert first == second
    assert first.content_hash == second.content_hash
    assert [(job.target_id, job.snapshot_id) for job in first.jobs] == [
        ("alpha", "alpha-v1"),
        ("beta", "beta-v1"),
    ]
    assert {job.evaluator_id for job in first.jobs} == {"synthetic-rules-v1"}
    payload = lock_as_dict(first)
    assert payload["content_hash"] == first.content_hash
    assert len(payload["jobs"]) == 2


def test_experiment_lock_round_trips_and_rejects_tampering() -> None:
    repository = ConfigurationRepository.from_file(FIXTURE)
    payload = lock_as_dict(plan_experiment(repository, "two-targets"))
    assert ExperimentLock.from_mapping(payload).content_hash == payload["content_hash"]

    tampered = deepcopy(payload)
    tampered["jobs"][0]["provider_id"] = "different-provider"
    with pytest.raises(ConfigurationError, match="identity or hash"):
        ExperimentLock.from_mapping(tampered)


def test_lock_hashes_evaluator_code_calibration_and_authored_case_bytes(
    tmp_path: Path,
) -> None:
    workspace_root = tmp_path / "workspace"
    shutil.copytree(FIXTURE.parent, workspace_root)
    repository = ConfigurationRepository.from_file(workspace_root / "workspace.yaml")
    baseline = plan_experiment(repository, "two-targets")
    evaluator_hash = repository.document_hash("evaluators", "synthetic-rules-v1")
    suite_hash = repository.document_hash("suites", "synthetic")

    plugin = workspace_root / "evaluators/synthetic/plugin.py"
    plugin.write_text(plugin.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert repository.document_hash("evaluators", "synthetic-rules-v1") != evaluator_hash
    evaluator_changed = plan_experiment(repository, "two-targets")
    assert evaluator_changed.content_hash != baseline.content_hash

    code_hash = repository.document_hash("evaluators", "synthetic-rules-v1")
    calibration = workspace_root / "evaluators/synthetic/calibration/ideal.md"
    calibration.write_text(
        calibration.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    assert repository.document_hash("evaluators", "synthetic-rules-v1") != code_hash
    calibration_changed = plan_experiment(repository, "two-targets")
    assert calibration_changed.content_hash != evaluator_changed.content_hash

    prompt = workspace_root / "suites/synthetic/units/coding/cases/coding-001/prompt.md"
    prompt.write_text(prompt.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert repository.document_hash("suites", "synthetic") != suite_hash
    assert (
        plan_experiment(repository, "two-targets").content_hash
        != calibration_changed.content_hash
    )
