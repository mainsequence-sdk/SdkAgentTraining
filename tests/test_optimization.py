from __future__ import annotations

import os
from pathlib import Path

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
from ms_agent_eval.core.models import (
    EvaluatorIdentity,
    OptimizerProfile,
    ProgramSpecification,
    SplitAssignment,
    SplitManifest,
)
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.programs.dspy import (
    BudgetExceeded,
    BudgetLedger,
    BudgetLimits,
    GovernedDspyOptimizer,
    OptimizationCase,
    ProtectedSplitDataset,
    create_program,
    program_state,
)


class ExpectedEvaluator:
    identity = EvaluatorIdentity("synthetic.expected-v1", "rule-based-checklist", "1")

    def __init__(self, expected: dict[str, str]) -> None:
        self.expected = expected

    def evaluate(self, context: EvaluationContext) -> EvaluationDraft:
        score = float(context.response_text == self.expected[context.case.id])
        return EvaluationDraft((CriterionScore("correct", score, "exact"),))


def _definition(root: Path, case_id: str) -> CaseDefinition:
    path = root / case_id
    path.mkdir(parents=True)
    (path / "case.yaml").write_text(
        f"id: {case_id}\n"
        "evaluator:\n"
        "  name: synthetic.expected-v1\n"
        "  method: rule-based-checklist\n"
        "  status: active\n",
        encoding="utf-8",
    )
    (path / "rubric.yaml").write_text(
        "passing_score: 1.0\ncriteria:\n"
        "  - id: correct\n"
        "    weight: 1.0\n"
        "    description: Exact response.\n",
        encoding="utf-8",
    )
    return CaseDefinition.load(path)


def _profile() -> OptimizerProfile:
    return OptimizerProfile.from_mapping(
        {
            "schema_version": 1,
            "id": "few-shot-small",
            "engine": "dspy",
            "optimizer": "LabeledFewShot",
            "parameters": {"k": 2},
            "budgets": {
                "model_calls": 20,
                "configured_cost": 1.0,
                "tokens": 1000,
                "wall_seconds": 60,
                "concurrency": 1,
            },
        }
    )


def _specification() -> ProgramSpecification:
    return ProgramSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "instruction-response-v1",
            "engine": "dspy",
            "payload": {"module": "predict", "adapter": "chat"},
        }
    )


def test_compile_cannot_load_held_out_and_promotion_is_explicit(tmp_path: Path) -> None:
    assignments = (
        SplitAssignment("case-train", "group-train", "train"),
        SplitAssignment("case-development", "group-development", "development"),
        SplitAssignment("case-test", "group-test", "test"),
        SplitAssignment("case-challenge", "group-challenge", "challenge"),
    )
    manifest = SplitManifest.create(id="synthetic-protected-v1", assignments=assignments)
    expected = {item.case_id: f"answer-{item.case_id}" for item in assignments}
    definitions = {
        item.case_id: _definition(tmp_path / "cases", item.case_id)
        for item in assignments
    }
    loaded_roles: list[str] = []

    def loader(assignment: SplitAssignment) -> OptimizationCase:
        loaded_roles.append(assignment.split)
        return OptimizationCase(
            definitions[assignment.case_id],
            assignment.group_id,
            assignment.split,
            "global",
            "instruction",
            f"task-{assignment.case_id}",
            expected[assignment.case_id],
        )

    evaluator = ExpectedEvaluator(expected)
    registry = EvaluatorRegistry()
    registry.register(
        evaluator,
        CalibrationRecord(evaluator.identity, "synthetic-calibration-v1", 1, 2, 1, True),
    )
    service = EvaluationService(registry)
    dataset = ProtectedSplitDataset(manifest, loader)
    artifacts = FilesystemArtifactStore(tmp_path / "external")
    optimizer = GovernedDspyOptimizer(artifacts)
    ledger = BudgetLedger(BudgetLimits.from_profile(_profile()))
    base = create_program()
    candidate = optimizer.compile_labeled_few_shot(
        base_program=base,
        specification=_specification(),
        profile=_profile(),
        protected_dataset=dataset,
        evaluation_service=service,
        provider_id="synthetic",
        ledger=ledger,
    )
    assert loaded_roles == ["train", "development"]
    assert candidate.manifest.state_format == "json"
    assert artifacts.verify(candidate.lock_artifact)
    assert artifacts.verify(candidate.manifest_artifact)
    assert candidate.compile_process_id != os.getpid()
    assert program_state(base)["predictors"][0]["demos"] == []
    assert program_state(candidate.program)["predictors"][0]["demos"]

    def predict(program, item, call_budget):  # type: ignore[no-untyped-def]
        call_budget.begin_call(0.0)
        call_budget.finish_call({"total_tokens": 1})
        demos = program_state(program)["predictors"][0]["demos"]
        return item.expected_response if demos else "incorrect"

    comparison = optimizer.compare_held_out(
        base_program=base,
        candidate=candidate,
        protected_dataset=dataset,
        evaluation_service=service,
        predictor=predict,
        ledger=ledger,
    )
    assert loaded_roles == ["train", "development", "test", "challenge"]
    assert comparison.base_mean == 0.0
    assert comparison.candidate_mean == 1.0
    assert comparison.eligible is True
    assert optimizer.promote(comparison, approved=False).promoted is False
    promoted = optimizer.promote(comparison, approved=True)
    assert promoted.promoted is True
    assert artifacts.verify(promoted.artifact)


def test_outer_budget_stops_calls_and_retains_snapshot() -> None:
    ledger = BudgetLedger(BudgetLimits(1, 0.1, 2, 60.0, 1))
    ledger.begin_call(0.1)
    with pytest.raises(BudgetExceeded, match="concurrency"):
        ledger.begin_call(0.0)
    ledger.finish_call({"total_tokens": 2})
    with pytest.raises(BudgetExceeded, match="model_calls") as error:
        ledger.begin_call(0.0)
    assert error.value.snapshot.model_calls == 1
    assert error.value.snapshot.tokens == 2
