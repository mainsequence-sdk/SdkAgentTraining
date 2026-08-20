from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import yaml
from ms_agent_eval.core.evaluation import (
    CalibrationRecord,
    CaseDefinition,
    CriterionScore,
    EvaluationContext,
    EvaluationDraft,
    EvaluationService,
    EvaluatorRegistry,
)
from ms_agent_eval.core.evaluator_plugins import resolve_workspace_path
from ms_agent_eval.core.errors import IntegrityError
from ms_agent_eval.core.models import EvaluatorIdentity


class OrchestrationRecurringArtifactEvaluator:
    identity = EvaluatorIdentity(
        "mainsequence.orchestration-recurring-artifact-v1",
        "rule-based-checklist",
        "1",
    )

    def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
        text = context.response_text.lower()
        unsafe_manual = any(
            phrase in text
            for phrase in (
                "ad hoc manual job",
                "one-off job",
                "only lives on one laptop",
            )
        )
        unsafe_local = any(
            phrase in text
            for phrase in (
                "local file path",
                "path to the csv file in the repository",
                "csv file in the repository",
            )
        )
        unsafe_strict = any(
            phrase in text
            for phrase in ("always use --strict", "must use --strict", "enable --strict")
        )
        no_verification = any(
            phrase in text for phrase in ("no need to verify", "verification is unnecessary")
        )

        workflow = (
            "scheduled_jobs.yaml" in text
            and any(term in text for term in ("version-controlled", "repository-managed"))
            and not unsafe_manual
        )
        artifact = (
            "artifact" in text
            and any(term in text for term in ("vendor", "csv", "input file"))
            and not unsafe_local
        )
        pinned = "related_image_id" in text and any(
            term in text for term in ("pinned", "image id", "immutable image")
        )
        strict = (
            "--strict" in text
            and any(term in text for term in ("do not", "avoid", "only when", "unless"))
            and not unsafe_strict
        )
        verification = (
            "project jobs list" in text
            and "project jobs runs list" in text
            and "project jobs runs logs" in text
            and not no_verification
        )
        concrete = (
            "jobs:" in text
            and "execution_path" in text
            and any(term in text for term in ("crontab", "schedule"))
        )
        values = {
            "workflow-choice": workflow,
            "artifact-handling": artifact,
            "pinned-image": pinned,
            "strict-safety": strict,
            "verification": verification,
            "concrete-example": concrete,
        }
        failed = [criterion_id for criterion_id, passed in values.items() if not passed]
        return EvaluationDraft(
            criteria=tuple(
                CriterionScore(
                    criterion_id,
                    1.0 if passed else 0.0,
                    "satisfied" if passed else "required evidence missing or contradicted",
                )
                for criterion_id, passed in values.items()
            ),
            feedback=None if not failed else f"Failed criteria: {', '.join(failed)}",
            limitations=(
                "Lexical rules verify this documentation-grounded contract; they do not "
                "execute platform commands.",
            ),
        )


def calibrate(
    evaluator: OrchestrationRecurringArtifactEvaluator,
    case: CaseDefinition,
    fixtures: Path,
) -> CalibrationRecord:
    manifest = yaml.safe_load((fixtures / "manifest.yaml").read_text(encoding="utf-8"))
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("fixtures"), list):
        raise IntegrityError("calibration manifest is invalid")
    positive = negative = adversarial = 0
    failures = []
    for item in manifest["fixtures"]:
        if not isinstance(item, Mapping):
            raise IntegrityError("calibration fixture entry is invalid")
        response = (fixtures / str(item["file"])).read_text(encoding="utf-8")
        draft = evaluator.evaluate(EvaluationContext(case, response))
        criteria = EvaluationService._validate_draft(case, draft)
        weights = {criterion.id: criterion.weight for criterion in case.criteria}
        score = sum(value.score * weights[value.id] for value in criteria)
        passed = score >= case.passing_score
        expected = bool(item["passed"])
        if passed != expected:
            failures.append(f"{item['file']}: expected {expected}, got {passed} ({score})")
        if expected:
            positive += 1
        else:
            negative += 1
        if bool(item.get("adversarial", False)):
            adversarial += 1
    if failures:
        raise IntegrityError("calibration failures: " + "; ".join(failures))
    record = CalibrationRecord(
        evaluator.identity,
        "mainsequence.orchestration-recurring-artifact-v1-calibration-v1",
        positive,
        negative,
        adversarial,
        True,
    )
    record.validate()
    return record


def build_registry(
    *, workspace_root: Path, configuration: Mapping[str, object]
) -> EvaluatorRegistry:
    case = CaseDefinition.load(
        resolve_workspace_path(workspace_root, configuration, "calibration_case")
    )
    fixtures = resolve_workspace_path(
        workspace_root, configuration, "calibration_fixtures"
    )
    evaluator = OrchestrationRecurringArtifactEvaluator()
    registry = EvaluatorRegistry()
    registry.register(evaluator, calibrate(evaluator, case, fixtures))
    return registry
