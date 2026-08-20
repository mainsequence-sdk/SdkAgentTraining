from __future__ import annotations

from pathlib import Path

import dspy
import pytest
from ms_agent_eval.core.evaluation import (
    CalibrationRecord,
    CaseDefinition,
    CriterionScore,
    EvaluationContext,
    EvaluationDraft,
    EvaluationService,
    EvaluatorRegistry,
)
from ms_agent_eval.core.models import EvaluatorIdentity
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.programs.dspy import DspyMetricAdapter, MetricEvaluationError


class ExactEvaluator:
    identity = EvaluatorIdentity("synthetic.exact-v1", "rule-based-checklist", "1")

    def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
        score = 1.0 if context.response_text == "correct" else 0.0
        return EvaluationDraft((CriterionScore("correct", score, "exact match"),))


def _case(tmp_path: Path) -> CaseDefinition:
    case_path = tmp_path / "case"
    case_path.mkdir()
    (case_path / "case.yaml").write_text(
        "id: synthetic-001\n"
        "evaluator:\n"
        "  name: synthetic.exact-v1\n"
        "  method: rule-based-checklist\n"
        "  status: active\n",
        encoding="utf-8",
    )
    (case_path / "rubric.yaml").write_text(
        "passing_score: 1.0\ncriteria:\n"
        "  - id: correct\n"
        "    weight: 1.0\n"
        "    description: Exact response.\n",
        encoding="utf-8",
    )
    return CaseDefinition.load(case_path)


def _service() -> EvaluationService:
    evaluator = ExactEvaluator()
    registry = EvaluatorRegistry()
    registry.register(
        evaluator,
        CalibrationRecord(evaluator.identity, "synthetic-calibration-v1", 1, 2, 1, True),
    )
    return EvaluationService(registry)


def test_metric_projects_one_authoritative_external_evaluation(tmp_path: Path) -> None:
    case = _case(tmp_path)
    store = FilesystemArtifactStore(tmp_path / "external")
    metric = DspyMetricAdapter(
        service=_service(),
        cases={case.id: case},
        artifacts=store,
        projection="score_with_feedback",
    )
    projected = metric(
        dspy.Example(case_id=case.id),
        dspy.Prediction(response="correct"),
    )
    assert projected.score == 1.0
    assert len(metric.records) == 1
    evaluation, reference = metric.records[0]
    assert evaluation.score == projected.score
    assert store.verify(reference)


def test_metric_never_turns_evaluator_failure_into_zero(tmp_path: Path) -> None:
    class BrokenEvaluator(ExactEvaluator):
        def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
            del context
            raise RuntimeError("broken evaluator")

    case = _case(tmp_path)
    evaluator = BrokenEvaluator()
    registry = EvaluatorRegistry()
    registry.register(
        evaluator,
        CalibrationRecord(evaluator.identity, "synthetic-calibration-v1", 1, 2, 1, True),
    )
    metric = DspyMetricAdapter(
        service=EvaluationService(registry),
        cases={case.id: case},
        artifacts=FilesystemArtifactStore(tmp_path / "external"),
    )
    with pytest.raises(MetricEvaluationError, match="evaluator_error"):
        metric(dspy.Example(case_id=case.id), dspy.Prediction(response="anything"))
