from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.errors import PreflightError
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationService
from ms_agent_eval.core.evaluator_plugins import load_evaluator_registry
from ms_agent_eval.core.models import SplitAssignment, SplitManifest, SuiteSpecification
from ms_agent_eval.programs.dspy import OptimizationCase, ProtectedSplitDataset


ROOT = Path(__file__).parents[1]
PACK = ROOT / "experiments/mainsequence-sdk"


def test_mainsequence_optimization_fails_until_train_and_development_are_evaluable() -> None:
    repository = ConfigurationRepository.from_file(PACK / "workspace.yaml")
    suite = SuiteSpecification.from_mapping(
        yaml.safe_load((PACK / "suites/v2/suite.yaml").read_text(encoding="utf-8"))
    )
    split = SplitManifest.from_mapping(
        json.loads((PACK / "suites/v2/split.json").read_text(encoding="utf-8"))
    )
    paths = {item.id: PACK / item.path for item in suite.cases}
    service = EvaluationService(load_evaluator_registry(repository, "mainsequence-rules-v1"))

    def loader(assignment: SplitAssignment) -> OptimizationCase:
        path = paths[assignment.case_id]
        return OptimizationCase(
            CaseDefinition.load(path),
            assignment.group_id,
            assignment.split,
            "locked global context",
            "locked instruction context",
            (path / "prompt.md").read_text(encoding="utf-8"),
            (path / "expected/response.md").read_text(encoding="utf-8"),
        )

    with pytest.raises(PreflightError, match="no model request was sent"):
        ProtectedSplitDataset(split, loader).optimizer_view(service)
