from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .errors import ConfigurationError
from .hashing import content_hash


@dataclass(frozen=True)
class ReportRecord:
    run_id: str
    experiment_lock_hash: str
    source_commit: str
    case_id: str
    case_hash: str
    split: str
    solver_model_hash: str
    solver_program_hash: str
    judge_model_hash: str
    judge_program_hash: str
    calibration_hash: str
    score: float
    passed: bool
    solver_calls: int
    judge_calls: int
    tokens: int
    configured_cost: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ReportRecord:
        strings = {}
        for field in (
            "run_id",
            "experiment_lock_hash",
            "source_commit",
            "case_id",
            "case_hash",
            "split",
            "solver_model_hash",
            "solver_program_hash",
            "judge_model_hash",
            "judge_program_hash",
            "calibration_hash",
        ):
            value = payload.get(field)
            if not isinstance(value, str) or not value:
                raise ConfigurationError(f"report {field} must be non-empty")
            strings[field] = value
        score = payload.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ConfigurationError("report score must be numeric")
        passed = payload.get("passed")
        if not isinstance(passed, bool):
            raise ConfigurationError("report passed must be boolean")
        integers = {}
        for field in ("solver_calls", "judge_calls", "tokens"):
            value = payload.get(field, 0)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise ConfigurationError(f"report {field} must be non-negative")
            integers[field] = value
        cost = payload.get("configured_cost", 0.0)
        if not isinstance(cost, (int, float)) or isinstance(cost, bool) or cost < 0:
            raise ConfigurationError("report configured_cost must be non-negative")
        return cls(
            **strings,
            score=float(score),
            passed=passed,
            **integers,
            configured_cost=float(cost),
        )


_EVALUATION_IDENTITY = (
    "source_commit",
    "case_hash",
    "split",
    "judge_model_hash",
    "judge_program_hash",
    "calibration_hash",
)


class SummaryReporter:
    def summarize(self, records: Sequence[ReportRecord]) -> dict[str, object]:
        if not records:
            raise ConfigurationError("a report requires at least one record")
        groups: dict[tuple[object, ...], list[ReportRecord]] = defaultdict(list)
        for record in records:
            key = (
                record.experiment_lock_hash,
                record.solver_model_hash,
                record.solver_program_hash,
                record.judge_model_hash,
                record.judge_program_hash,
                record.calibration_hash,
                record.split,
            )
            groups[key].append(record)
        results = []
        for identity, items in sorted(groups.items(), key=lambda item: str(item[0])):
            results.append(
                {
                    "identity": identity,
                    "case_count": len(items),
                    "mean_score": sum(item.score for item in items) / len(items),
                    "pass_rate": sum(item.passed for item in items) / len(items),
                    "solver_calls": sum(item.solver_calls for item in items),
                    "judge_calls": sum(item.judge_calls for item in items),
                    "tokens": sum(item.tokens for item in items),
                    "configured_cost": sum(item.configured_cost for item in items),
                }
            )
        return {
            "schema_version": 2,
            "kind": "summary",
            "record_count": len(records),
            "groups": results,
            "content_hash": content_hash(results),
        }

    def regression(
        self,
        baseline: Sequence[ReportRecord],
        candidate: Sequence[ReportRecord],
    ) -> dict[str, object]:
        left = {item.case_id: item for item in baseline}
        right = {item.case_id: item for item in candidate}
        if set(left) != set(right):
            raise ConfigurationError("regression inputs must contain identical case ids")
        cases = []
        for case_id in sorted(left):
            baseline_record = left[case_id]
            candidate_record = right[case_id]
            for field in _EVALUATION_IDENTITY:
                if getattr(baseline_record, field) != getattr(candidate_record, field):
                    raise ConfigurationError(
                        f"regression evaluation identity {field} differs for {case_id}"
                    )
            delta = candidate_record.score - baseline_record.score
            cases.append(
                {
                    "case_id": case_id,
                    "baseline_score": baseline_record.score,
                    "candidate_score": candidate_record.score,
                    "delta": delta,
                    "regression": delta < 0,
                }
            )
        return {
            "schema_version": 2,
            "kind": "regression",
            "cases": cases,
            "regression_count": sum(item["regression"] for item in cases),
            "content_hash": content_hash(cases),
        }
