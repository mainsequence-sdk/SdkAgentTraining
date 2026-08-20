from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError
from .hashing import content_hash
from .legacy import load_legacy_json


@dataclass(frozen=True)
class ReportRecord:
    case_id: str
    suite_id: str
    suite_version: str
    target_id: str
    source_commit: str
    snapshot_id: str
    bundle_id: str
    unit_id: str
    program_id: str
    engine: str
    module: str
    adapter: str
    compiled_artifact: str
    dspy_version: str | None
    optimizer_lock: str | None
    split_role: str
    provider_id: str
    model: str
    parameters_hash: str
    evaluator_name: str
    evaluator_version: str
    status: str
    score: float | None
    passed: bool | None
    configured_cost: float
    tokens: int
    latency_seconds: float

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> ReportRecord:
        required_strings = (
            "case_id",
            "suite_id",
            "suite_version",
            "target_id",
            "source_commit",
            "snapshot_id",
            "bundle_id",
            "unit_id",
            "program_id",
            "engine",
            "module",
            "adapter",
            "compiled_artifact",
            "split_role",
            "provider_id",
            "model",
            "parameters_hash",
            "evaluator_name",
            "evaluator_version",
            "status",
        )
        values: dict[str, object] = {}
        for field_name in required_strings:
            value = payload.get(field_name)
            if not isinstance(value, str) or not value:
                raise ConfigurationError(f"report record {field_name} must be non-empty")
            values[field_name] = value
        score = payload.get("score")
        passed = payload.get("passed")
        if score is not None and (
            not isinstance(score, (int, float)) or isinstance(score, bool)
        ):
            raise ConfigurationError("report score must be numeric or null")
        if passed is not None and not isinstance(passed, bool):
            raise ConfigurationError("report passed must be boolean or null")
        for optional in ("dspy_version", "optimizer_lock"):
            value = payload.get(optional)
            if value is not None and not isinstance(value, str):
                raise ConfigurationError(f"report {optional} must be a string or null")
            values[optional] = value
        for field_name in ("configured_cost", "latency_seconds"):
            value = payload.get(field_name, 0.0)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ConfigurationError(f"report {field_name} must be non-negative")
            values[field_name] = float(value)
        tokens = payload.get("tokens", 0)
        if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
            raise ConfigurationError("report tokens must be a non-negative integer")
        values.update(score=float(score) if score is not None else None, passed=passed, tokens=tokens)
        return cls(**values)  # type: ignore[arg-type]


_GROUP_FIELDS = (
    "suite_id",
    "suite_version",
    "target_id",
    "source_commit",
    "snapshot_id",
    "bundle_id",
    "unit_id",
    "program_id",
    "engine",
    "module",
    "adapter",
    "compiled_artifact",
    "dspy_version",
    "optimizer_lock",
    "split_role",
    "provider_id",
    "model",
    "parameters_hash",
    "evaluator_name",
    "evaluator_version",
)


class SummaryReporter:
    def summarize(self, records: Sequence[ReportRecord]) -> dict[str, object]:
        if not records:
            raise ConfigurationError("a report requires at least one record")
        groups: dict[tuple[object, ...], list[ReportRecord]] = defaultdict(list)
        for record in records:
            groups[tuple(getattr(record, field) for field in _GROUP_FIELDS)].append(record)
        results = []
        for identity, items in sorted(groups.items(), key=lambda item: str(item[0])):
            scored = [item for item in items if item.score is not None]
            passed = [item for item in scored if item.passed is True]
            results.append(
                {
                    "identity": dict(zip(_GROUP_FIELDS, identity, strict=True)),
                    "case_count": len(items),
                    "evaluated_count": len(scored),
                    "mean_score": (
                        sum(float(item.score) for item in scored) / len(scored)
                        if scored
                        else None
                    ),
                    "pass_rate": len(passed) / len(scored) if scored else None,
                    "configured_cost": sum(item.configured_cost for item in items),
                    "tokens": sum(item.tokens for item in items),
                    "latency_seconds": sum(item.latency_seconds for item in items),
                }
            )
        warnings = sorted(
            {
                "legacy record has unresolved source revision"
                for record in records
                if record.source_commit == "unresolved"
            }
        )
        return {
            "schema_version": 1,
            "report_kind": "summary",
            "record_count": len(records),
            "groups": results,
            "warnings": warnings,
            "content_hash": content_hash(results),
        }

    def regression(
        self,
        baseline: Sequence[ReportRecord],
        candidate: Sequence[ReportRecord],
    ) -> dict[str, object]:
        baseline_cases = {item.case_id: item for item in baseline}
        candidate_cases = {item.case_id: item for item in candidate}
        if set(baseline_cases) != set(candidate_cases):
            raise ConfigurationError("regression inputs must contain identical case ids")
        cases = []
        for case_id in sorted(baseline_cases):
            left = baseline_cases[case_id]
            right = candidate_cases[case_id]
            for field in (
                "suite_id",
                "suite_version",
                "target_id",
                "source_commit",
                "snapshot_id",
                "bundle_id",
                "unit_id",
                "split_role",
                "provider_id",
                "model",
                "evaluator_name",
                "evaluator_version",
            ):
                if getattr(left, field) != getattr(right, field):
                    raise ConfigurationError(
                        f"regression axis {field} differs for case {case_id}"
                    )
            delta = (
                right.score - left.score
                if left.score is not None and right.score is not None
                else None
            )
            cases.append(
                {
                    "case_id": case_id,
                    "baseline_score": left.score,
                    "candidate_score": right.score,
                    "delta": delta,
                    "regression": delta is not None and delta < 0,
                }
            )
        return {
            "schema_version": 1,
            "report_kind": "regression",
            "cases": cases,
            "regression_count": sum(bool(item["regression"]) for item in cases),
            "content_hash": content_hash(cases),
        }


def read_legacy_run(run_root: Path) -> tuple[ReportRecord, ...]:
    """Adapt a legacy schema-v0 run to honest, explicitly unresolved report records."""

    manifest = load_legacy_json(run_root / "manifest.json")
    sdk = manifest.get("sdk")
    agent = manifest.get("agent")
    paths = manifest.get("paths")
    if not isinstance(sdk, Mapping) or not isinstance(agent, Mapping) or not isinstance(paths, Mapping):
        raise ConfigurationError("legacy run manifest lacks sdk/agent/paths mappings")
    evaluations_root = run_root / str(paths.get("evaluations", "evaluations"))
    skills_root = run_root / str(paths.get("skills", "skills"))
    records = []
    for evaluation_path in sorted(evaluations_root.glob("*.json")):
        evaluation = load_legacy_json(evaluation_path)
        case_id = str(evaluation.get("case_id", evaluation_path.stem))
        response = next(skills_root.glob(f"**/{case_id}/response.md"), None)
        unit_id = (
            response.parent.parent.relative_to(skills_root).as_posix()
            if response is not None
            else "unresolved"
        )
        evaluator = evaluation.get("evaluator")
        evaluator = evaluator if isinstance(evaluator, Mapping) else {}
        score = evaluation.get("total_score")
        records.append(
            ReportRecord.from_mapping(
                {
                    "case_id": case_id,
                    "suite_id": "legacy-unversioned",
                    "suite_version": "0",
                    "target_id": f"legacy-{sdk.get('package', 'unknown')}",
                    "source_commit": "unresolved",
                    "snapshot_id": f"legacy-{sdk.get('version', 'unknown')}",
                    "bundle_id": "legacy",
                    "unit_id": unit_id,
                    "program_id": "legacy-raw-unknown",
                    "engine": "raw_messages",
                    "module": "legacy",
                    "adapter": "legacy",
                    "compiled_artifact": "uncompiled",
                    "dspy_version": None,
                    "optimizer_lock": None,
                    "split_role": "legacy-unassigned",
                    "provider_id": str(agent.get("provider", "unknown")),
                    "model": str(agent.get("model", "unknown")),
                    "parameters_hash": "unresolved",
                    "evaluator_name": str(evaluator.get("name", "unknown")),
                    "evaluator_version": "legacy-unknown",
                    "status": "evaluated" if isinstance(score, (int, float)) else "unknown",
                    "score": score,
                    "passed": evaluation.get("passed"),
                    "configured_cost": 0.0,
                    "tokens": 0,
                    "latency_seconds": 0.0,
                }
            )
        )
    if not records:
        raise ConfigurationError(f"legacy run has no evaluation JSON: {run_root}")
    return tuple(records)
