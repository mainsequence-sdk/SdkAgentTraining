from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

import yaml

from .errors import ConfigurationError, IntegrityError, PreflightError
from .models import EvaluationStatus, EvaluatorIdentity


class CaseEvaluatorStatus(str, Enum):
    ACTIVE = "active"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    NOT_EVALUABLE = "not_evaluable"


_METHODS = {"rule-based-checklist", "human-review", "none"}


@dataclass(frozen=True)
class CaseEvaluatorMetadata:
    name: str
    method: str
    status: CaseEvaluatorStatus

    @classmethod
    def from_mapping(
        cls, payload: Mapping[str, object], *, path: Path
    ) -> CaseEvaluatorMetadata:
        name = payload.get("name")
        method = payload.get("method")
        try:
            status = CaseEvaluatorStatus(payload.get("status"))
        except (TypeError, ValueError) as error:
            raise ConfigurationError("invalid evaluator.status", path=path) from error
        if not isinstance(name, str) or not name:
            raise ConfigurationError("evaluator.name must be non-empty", path=path)
        if method not in _METHODS:
            raise ConfigurationError("invalid evaluator.method", path=path)
        expected_method = {
            CaseEvaluatorStatus.ACTIVE: "rule-based-checklist",
            CaseEvaluatorStatus.MANUAL_REVIEW_REQUIRED: "human-review",
            CaseEvaluatorStatus.NOT_EVALUABLE: "none",
        }[status]
        if method != expected_method:
            raise ConfigurationError(
                f"{status.value} evaluator must use {expected_method}", path=path
            )
        return cls(name, method, status)


@dataclass(frozen=True)
class RubricCriterion:
    id: str
    weight: float
    description: str


@dataclass(frozen=True)
class CaseDefinition:
    id: str
    path: Path
    evaluator: CaseEvaluatorMetadata
    passing_score: float
    criteria: tuple[RubricCriterion, ...]

    @classmethod
    def load(cls, case_directory: Path) -> CaseDefinition:
        case_file = case_directory / "case.yaml"
        rubric_file = case_directory / "rubric.yaml"
        case_payload = _yaml_mapping(case_file)
        rubric_payload = _yaml_mapping(rubric_file)
        evaluator_payload = case_payload.get("evaluator")
        if not isinstance(evaluator_payload, Mapping):
            raise ConfigurationError("case requires evaluator metadata", path=case_file)
        raw_criteria = rubric_payload.get("criteria")
        if not isinstance(raw_criteria, Sequence) or isinstance(raw_criteria, (str, bytes)):
            raise ConfigurationError("rubric criteria must be a list", path=rubric_file)
        criteria = []
        for item in raw_criteria:
            if not isinstance(item, Mapping):
                raise ConfigurationError("rubric criterion must be a mapping", path=rubric_file)
            criterion_id = item.get("id")
            weight = item.get("weight")
            description = item.get("description")
            if not isinstance(criterion_id, str) or not criterion_id:
                raise ConfigurationError("rubric criterion id is invalid", path=rubric_file)
            if not isinstance(weight, (int, float)) or isinstance(weight, bool):
                raise ConfigurationError("rubric criterion weight is invalid", path=rubric_file)
            if not isinstance(description, str):
                raise ConfigurationError(
                    "rubric criterion description is invalid", path=rubric_file
                )
            criteria.append(RubricCriterion(criterion_id, float(weight), description))
        if not criteria or abs(sum(item.weight for item in criteria) - 1.0) > 1e-9:
            raise ConfigurationError("rubric criterion weights must sum to 1.0", path=rubric_file)
        passing_score = rubric_payload.get("passing_score")
        if (
            not isinstance(passing_score, (int, float))
            or isinstance(passing_score, bool)
            or not 0 <= float(passing_score) <= 1
        ):
            raise ConfigurationError("rubric passing_score must be in [0, 1]", path=rubric_file)
        case_id = case_payload.get("id")
        if not isinstance(case_id, str) or not case_id:
            raise ConfigurationError("case id must be non-empty", path=case_file)
        return cls(
            case_id,
            case_directory,
            CaseEvaluatorMetadata.from_mapping(evaluator_payload, path=case_file),
            float(passing_score),
            tuple(criteria),
        )


def _yaml_mapping(path: Path) -> Mapping[str, object]:
    if not path.is_file():
        raise ConfigurationError("required case document is missing", path=path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ConfigurationError("case document must contain a mapping", path=path)
    return payload


@dataclass(frozen=True)
class EvaluationContext:
    case: CaseDefinition
    response_text: str


@dataclass(frozen=True)
class CriterionScore:
    id: str
    score: float
    notes: str


@dataclass(frozen=True)
class EvaluationDraft:
    criteria: tuple[CriterionScore, ...]
    feedback: str | None = None
    limitations: tuple[str, ...] = ()


class Evaluator(Protocol):
    identity: EvaluatorIdentity

    def evaluate(self, context: EvaluationContext) -> EvaluationDraft: ...


@dataclass(frozen=True)
class CalibrationRecord:
    evaluator: EvaluatorIdentity
    calibration_id: str
    positive_fixtures: int
    negative_fixtures: int
    adversarial_fixtures: int
    passed: bool

    def validate(self) -> None:
        if (
            not self.passed
            or self.positive_fixtures < 1
            or self.negative_fixtures < 2
            or self.adversarial_fixtures < 1
        ):
            raise IntegrityError(
                f"evaluator {self.evaluator.name!r} lacks passing calibration coverage"
            )


class EvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, Evaluator] = {}
        self._calibrations: dict[str, CalibrationRecord] = {}

    def register(self, evaluator: Evaluator, calibration: CalibrationRecord) -> None:
        name = evaluator.identity.name
        if name in self._evaluators:
            raise IntegrityError(f"duplicate evaluator registration: {name}")
        if calibration.evaluator != evaluator.identity:
            raise IntegrityError("calibration identity differs from evaluator identity")
        calibration.validate()
        self._evaluators[name] = evaluator
        self._calibrations[name] = calibration

    def get(self, name: str) -> Evaluator:
        try:
            return self._evaluators[name]
        except KeyError as error:
            raise PreflightError(f"active evaluator is not registered: {name}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._evaluators))

    def calibration(self, name: str) -> CalibrationRecord:
        try:
            return self._calibrations[name]
        except KeyError as error:
            raise PreflightError(f"active evaluator is not registered: {name}") from error


def validate_case_bank(
    case_root: Path, registry: EvaluatorRegistry
) -> dict[str, object]:
    """Validate case metadata and exact active-evaluator registration."""

    counts: Counter[str] = Counter()
    active: list[str] = []
    total = 0
    for case_file in sorted(case_root.rglob("case.yaml")):
        case = CaseDefinition.load(case_file.parent)
        total += 1
        counts[case.evaluator.status.value] += 1
        if case.evaluator.status is CaseEvaluatorStatus.ACTIVE:
            registered = registry.get(case.evaluator.name)
            if registered.identity.method != case.evaluator.method:
                raise IntegrityError(
                    f"evaluator method mismatch for {case.id}: "
                    f"{case.evaluator.method} != {registered.identity.method}"
                )
            active.append(case.evaluator.name)
    return {
        "status": "valid",
        "case_count": total,
        "evaluator_status_counts": dict(sorted(counts.items())),
        "active_evaluators": sorted(set(active)),
        "registered_evaluators": list(registry.names()),
    }


@dataclass(frozen=True)
class EvaluationPreflight:
    automatic: bool
    status: EvaluationStatus
    reason: str


@dataclass(frozen=True)
class EvaluationRecord:
    schema_version: int
    status: EvaluationStatus
    case_id: str
    evaluator: EvaluatorIdentity | None
    evaluated_at: str | None
    score: float | None
    passed: bool | None
    passing_score: float
    criteria: tuple[CriterionScore, ...]
    feedback: str | None
    limitations: tuple[str, ...]


class EvaluationService:
    def __init__(self, registry: EvaluatorRegistry) -> None:
        self.registry = registry

    def preflight(
        self, case: CaseDefinition, *, allow_unscored: bool = False
    ) -> EvaluationPreflight:
        metadata = case.evaluator
        if metadata.status is CaseEvaluatorStatus.ACTIVE:
            evaluator = self.registry.get(metadata.name)
            if (
                evaluator.identity.name != metadata.name
                or evaluator.identity.method != metadata.method
            ):
                raise PreflightError("case evaluator identity differs from registered code")
            return EvaluationPreflight(True, EvaluationStatus.EVALUATED, "registered")
        status = (
            EvaluationStatus.MANUAL_REVIEW_REQUIRED
            if metadata.status is CaseEvaluatorStatus.MANUAL_REVIEW_REQUIRED
            else EvaluationStatus.NOT_EVALUABLE
        )
        if not allow_unscored:
            raise PreflightError(
                f"case {case.id!r} is {metadata.status.value}; no model request was sent"
            )
        return EvaluationPreflight(False, status, metadata.status.value)

    def evaluate(
        self,
        case: CaseDefinition,
        response_text: str,
        *,
        allow_unscored: bool = False,
        now: datetime | None = None,
    ) -> EvaluationRecord:
        decision = self.preflight(case, allow_unscored=allow_unscored)
        if not decision.automatic:
            return EvaluationRecord(
                1,
                decision.status,
                case.id,
                EvaluatorIdentity(case.evaluator.name, case.evaluator.method, "unscored"),
                None,
                None,
                None,
                case.passing_score,
                (),
                "No calibrated automatic evaluator is available for this case.",
                (),
            )
        evaluator = self.registry.get(case.evaluator.name)
        try:
            draft = evaluator.evaluate(EvaluationContext(case, response_text))
            criteria = self._validate_draft(case, draft)
            weights = {item.id: item.weight for item in case.criteria}
            score = sum(item.score * weights[item.id] for item in criteria)
            return EvaluationRecord(
                1,
                EvaluationStatus.EVALUATED,
                case.id,
                evaluator.identity,
                (now or datetime.now(UTC)).astimezone(UTC).isoformat(),
                score,
                score >= case.passing_score,
                case.passing_score,
                criteria,
                draft.feedback,
                draft.limitations,
            )
        except Exception as error:
            return EvaluationRecord(
                1,
                EvaluationStatus.EVALUATOR_ERROR,
                case.id,
                evaluator.identity,
                (now or datetime.now(UTC)).astimezone(UTC).isoformat(),
                None,
                None,
                case.passing_score,
                (),
                f"Evaluator failed: {type(error).__name__}",
                ("No score was emitted.",),
            )

    @staticmethod
    def _validate_draft(
        case: CaseDefinition, draft: EvaluationDraft
    ) -> tuple[CriterionScore, ...]:
        expected = {item.id for item in case.criteria}
        actual = {item.id for item in draft.criteria}
        if len(actual) != len(draft.criteria) or actual != expected:
            raise IntegrityError(
                f"evaluator criterion ids differ from rubric; expected={sorted(expected)}, "
                f"actual={sorted(actual)}"
            )
        for item in draft.criteria:
            if not 0 <= item.score <= 1:
                raise IntegrityError(f"criterion score outside [0, 1]: {item.id}")
        return draft.criteria
