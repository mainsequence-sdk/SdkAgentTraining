from __future__ import annotations

from pathlib import Path

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationService, validate_case_bank
from ms_agent_eval.core.evaluator_plugins import load_evaluator_registry
from ms_agent_eval.core.models import EvaluationStatus


ROOT = Path(__file__).parents[1]
REPOSITORY = ConfigurationRepository.from_file(
    ROOT / "experiments/mainsequence-sdk/workspace.yaml"
)
CASE = (
    ROOT
    / "experiments/mainsequence-sdk/suites/v2/units"
    / "platform_operations/orchestration_and_releases/cases"
    / "or-001-recurring-artifact-job"
)
FIXTURES = ROOT / "experiments/mainsequence-sdk/evaluators/mainsequence/calibration"
HISTORICAL = (
    ROOT
    / "tests/fixtures/legacy-run-v0"
    / "skills/platform_operations/orchestration_and_releases"
    / "or-001-recurring-artifact-job/response.md"
)


def test_calibration_has_positive_negative_and_adversarial_coverage() -> None:
    record = load_evaluator_registry(REPOSITORY, "mainsequence-rules-v1").calibration(
        "mainsequence.orchestration-recurring-artifact-v1"
    )
    assert record.passed
    assert record.positive_fixtures == 1
    assert record.negative_fixtures == 4
    assert record.adversarial_fixtures == 2


def test_all_calibration_expectations_are_enforced() -> None:
    case = CaseDefinition.load(CASE)
    service = EvaluationService(load_evaluator_registry(REPOSITORY, "mainsequence-rules-v1"))
    ideal = service.evaluate(case, (FIXTURES / "ideal.md").read_text(encoding="utf-8"))
    assert ideal.status is EvaluationStatus.EVALUATED and ideal.passed is True
    for name in (
        "partial-missing-artifact-input.md",
        "wrong-yaml-and-invented-cli.md",
        "contradictory-keyword-stuffing.md",
        "minimal-keyword-stuffing.md",
    ):
        result = service.evaluate(case, (FIXTURES / name).read_text(encoding="utf-8"))
        assert result.passed is False, name


def test_historical_incorrect_response_remains_failed() -> None:
    case = CaseDefinition.load(CASE)
    service = EvaluationService(load_evaluator_registry(REPOSITORY, "mainsequence-rules-v1"))
    result = service.evaluate(case, HISTORICAL.read_text(encoding="utf-8"))
    assert result.status is EvaluationStatus.EVALUATED
    assert result.passed is False


def test_namespaced_case_bank_validates_against_exact_registry() -> None:
    suite_root = ROOT / "experiments" / "mainsequence-sdk" / "suites" / "v2"
    report = validate_case_bank(
        suite_root, load_evaluator_registry(REPOSITORY, "mainsequence-rules-v1")
    )
    assert report["case_count"] == 74
    assert report["active_evaluators"] == [
        "mainsequence.orchestration-recurring-artifact-v1"
    ]
