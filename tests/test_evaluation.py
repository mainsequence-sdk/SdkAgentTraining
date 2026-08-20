from __future__ import annotations

from pathlib import Path

import pytest

from ms_agent_eval.core.errors import IntegrityError, PreflightError
from ms_agent_eval.core.evaluation import (
    CalibrationRecord,
    CaseDefinition,
    CriterionScore,
    EvaluationContext,
    EvaluationDraft,
    EvaluationService,
    EvaluatorRegistry,
)
from ms_agent_eval.core.models import EvaluationStatus, EvaluatorIdentity


class CompleteEvaluator:
    identity = EvaluatorIdentity("example.complete-v1", "rule-based-checklist", "1")

    def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
        del context
        return EvaluationDraft((CriterionScore("correct", 1.0, "ok"),))


def _case(tmp_path: Path, evaluator: str) -> CaseDefinition:
    directory = tmp_path / "case"
    directory.mkdir()
    (directory / "case.yaml").write_text(
        "id: example-001\n"
        "evaluator:\n"
        f"  name: {evaluator}\n"
        "  method: rule-based-checklist\n"
        "  status: active\n",
        encoding="utf-8",
    )
    (directory / "rubric.yaml").write_text(
        "passing_score: 0.8\n"
        "criteria:\n"
        "  - id: correct\n"
        "    weight: 1.0\n"
        "    description: Correct answer.\n",
        encoding="utf-8",
    )
    return CaseDefinition.load(directory)


def _registry() -> EvaluatorRegistry:
    evaluator = CompleteEvaluator()
    registry = EvaluatorRegistry()
    registry.register(
        evaluator,
        CalibrationRecord(evaluator.identity, "calibration-v1", 1, 2, 1, True),
    )
    return registry


def test_active_unknown_evaluator_fails_closed(tmp_path: Path) -> None:
    case = _case(tmp_path, "unknown")
    with pytest.raises(PreflightError, match="not registered"):
        EvaluationService(_registry()).preflight(case)


def test_registry_rejects_duplicate_and_uncalibrated_evaluators() -> None:
    evaluator = CompleteEvaluator()
    registry = _registry()
    with pytest.raises(IntegrityError, match="duplicate"):
        registry.register(
            evaluator,
            CalibrationRecord(evaluator.identity, "other", 1, 2, 1, True),
        )
    empty = EvaluatorRegistry()
    with pytest.raises(IntegrityError, match="calibration"):
        empty.register(
            evaluator,
            CalibrationRecord(evaluator.identity, "bad", 1, 1, 0, False),
        )


def test_evaluated_record_has_immutable_identity_and_score(tmp_path: Path) -> None:
    case = _case(tmp_path, CompleteEvaluator.identity.name)
    result = EvaluationService(_registry()).evaluate(case, "answer")
    assert result.status is EvaluationStatus.EVALUATED
    assert result.evaluator == CompleteEvaluator.identity
    assert result.score == 1.0
    assert result.passed is True


def test_bad_criterion_contract_becomes_evaluator_error(tmp_path: Path) -> None:
    class BadEvaluator(CompleteEvaluator):
        identity = EvaluatorIdentity("example.bad-v1", "rule-based-checklist", "1")

        def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
            del context
            return EvaluationDraft((CriterionScore("invented", 2.0, "bad"),))

    evaluator = BadEvaluator()
    registry = EvaluatorRegistry()
    registry.register(
        evaluator,
        CalibrationRecord(evaluator.identity, "calibration-v1", 1, 2, 1, True),
    )
    result = EvaluationService(registry).evaluate(_case(tmp_path, evaluator.identity.name), "x")
    assert result.status is EvaluationStatus.EVALUATOR_ERROR
    assert result.score is None and result.passed is None
