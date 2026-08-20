from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Literal

import dspy
from ms_agent_eval.core.errors import IntegrityError, ResolutionError
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationRecord, EvaluationService
from ms_agent_eval.core.hashing import canonical_json_bytes
from ms_agent_eval.core.models import ArtifactReference, EvaluationStatus
from ms_agent_eval.core.storage import ArtifactStore


class MetricEvaluationError(IntegrityError):
    """Raised when an authoritative evaluator cannot emit an optimization score."""


class DspyMetricAdapter:
    """Project authoritative framework evaluations into DSPy's metric contract."""

    def __init__(
        self,
        *,
        service: EvaluationService,
        cases: Mapping[str, CaseDefinition],
        artifacts: ArtifactStore,
        projection: Literal["score", "score_with_feedback"] = "score",
    ) -> None:
        if projection not in ("score", "score_with_feedback"):
            raise ValueError(f"unsupported DSPy metric projection: {projection}")
        self.service = service
        self.cases = dict(cases)
        self.artifacts = artifacts
        self.projection = projection
        self.records: list[tuple[EvaluationRecord, ArtifactReference]] = []

    def __call__(self, example: object, prediction: object, trace: object = None) -> object:
        del trace
        case_id = getattr(example, "case_id", None)
        if not isinstance(case_id, str) and isinstance(example, Mapping):
            case_id = example.get("case_id")
        if not isinstance(case_id, str) or case_id not in self.cases:
            raise ResolutionError(f"DSPy metric example has unknown case_id: {case_id!r}")
        response = getattr(prediction, "response", None)
        if not isinstance(response, str) and isinstance(prediction, Mapping):
            response = prediction.get("response")
        if not isinstance(response, str):
            raise MetricEvaluationError("DSPy prediction has no string response field")

        result = self.service.evaluate(self.cases[case_id], response)
        if result.status is not EvaluationStatus.EVALUATED or result.score is None:
            raise MetricEvaluationError(
                f"authoritative evaluator returned {result.status.value}; no metric emitted"
            )
        reference = self.artifacts.put_blob(
            BytesIO(canonical_json_bytes(result)), "application/json"
        )
        self.records.append((result, reference))
        if self.projection == "score":
            return result.score
        return dspy.Prediction(score=result.score, feedback=result.feedback or "")
