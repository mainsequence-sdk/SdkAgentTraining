from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationService
from ms_agent_eval.core.errors import PreflightError
from ms_agent_eval.core.evaluator_plugins import load_evaluator_registry
from ms_agent_eval.core.models import EvaluationStatus


ROOT = Path(__file__).parents[1]
V2 = ROOT / "experiments" / "mainsequence-sdk" / "suites" / "v2"
OR_CASE = (
    V2
    / "units/platform_operations/orchestration_and_releases/cases"
    / "or-001-recurring-artifact-job"
)


def test_every_v2_case_has_valid_explicit_evaluator_metadata() -> None:
    cases = [CaseDefinition.load(path.parent) for path in sorted(V2.rglob("case.yaml"))]
    assert len(cases) == 74
    counts = Counter(case.evaluator.status.value for case in cases)
    assert counts == {"active": 1, "manual_review_required": 5, "not_evaluable": 68}


def test_manual_case_fails_before_model_unless_unscored_is_explicit() -> None:
    repository = ConfigurationRepository.from_file(
        ROOT / "experiments/mainsequence-sdk/workspace.yaml"
    )
    service = EvaluationService(
        load_evaluator_registry(repository, "mainsequence-rules-v1")
    )
    manual_path = next(V2.rglob("dn-001-asset-risk-score-storage-first/case.yaml"))
    manual = CaseDefinition.load(manual_path.parent)
    called = False

    def model_call() -> None:
        nonlocal called
        called = True

    with pytest.raises(PreflightError, match="no model request was sent"):
        service.preflight(manual)
    assert called is False
    decision = service.preflight(manual, allow_unscored=True)
    model_call()
    result = service.evaluate(manual, "response", allow_unscored=True)
    assert decision.automatic is False
    assert result.status is EvaluationStatus.MANUAL_REVIEW_REQUIRED
    assert result.score is None and result.passed is None
    assert called is True
