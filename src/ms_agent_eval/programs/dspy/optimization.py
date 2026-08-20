from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import dspy
from ms_agent_eval.core.errors import ConfigurationError, IntegrityError, PreflightError
from ms_agent_eval.core.evaluation import CaseDefinition, EvaluationRecord, EvaluationService
from ms_agent_eval.core.hashing import canonical_json_bytes, content_hash, json_value
from ms_agent_eval.core.models import (
    ArtifactReference,
    CompiledProgramManifest,
    EvaluationStatus,
    OptimizerProfile,
    ProgramSpecification,
    SplitAssignment,
    SplitManifest,
)
from ms_agent_eval.core.storage import ArtifactStore

from .budget import BudgetLedger, BudgetSnapshot
from .engine import create_program, load_state_json, program_state, save_state_json


@dataclass(frozen=True)
class OptimizationCase:
    case: CaseDefinition
    group_id: str
    split: Literal["train", "development", "test", "challenge"]
    global_context: str
    instruction_context: str
    task: str
    expected_response: str

    def to_dspy_example(self) -> dspy.Example:
        return dspy.Example(
            global_context=self.global_context,
            instruction_context=self.instruction_context,
            task=self.task,
            response=self.expected_response,
        ).with_inputs("global_context", "instruction_context", "task")


@dataclass(frozen=True)
class OptimizerDatasetView:
    """Optimizer-visible examples; deliberately exposes no held-out loader or cases."""

    train: tuple[OptimizationCase, ...]
    development: tuple[OptimizationCase, ...]
    train_manifest_hash: str
    development_manifest_hash: str

    def train_examples(self) -> list[dspy.Example]:
        return [item.to_dspy_example() for item in self.train]


@dataclass(frozen=True)
class HeldOutDataset:
    cases: tuple[OptimizationCase, ...]
    manifest_hash: str


CaseLoader = Callable[[SplitAssignment], OptimizationCase]


class ProtectedSplitDataset:
    """Own the full split while handing optimizers only train/development data."""

    def __init__(self, manifest: SplitManifest, loader: CaseLoader) -> None:
        self.manifest = manifest
        self._loader = loader

    def optimizer_view(self, service: EvaluationService) -> OptimizerDatasetView:
        train = self._load_role("train", service)
        development = self._load_role("development", service)
        if not train or not development:
            raise PreflightError("optimization requires non-empty train and development splits")
        return OptimizerDatasetView(
            train,
            development,
            self._role_manifest_hash("train"),
            self._role_manifest_hash("development"),
        )

    def held_out_after_compile(
        self,
        compiled_manifest: CompiledProgramManifest,
        service: EvaluationService,
    ) -> HeldOutDataset:
        if compiled_manifest.state_format != "json" or not compiled_manifest.state_artifact:
            raise IntegrityError("held-out data requires a published JSON compiled artifact")
        test = self._load_role("test", service)
        challenge = self._load_role("challenge", service)
        if not test:
            raise PreflightError("held-out comparison requires a non-empty test split")
        cases = test + challenge
        return HeldOutDataset(
            cases,
            content_hash(
                {
                    "test": self._role_assignments("test"),
                    "challenge": self._role_assignments("challenge"),
                }
            ),
        )

    @property
    def held_out_assignment_hash(self) -> str:
        return content_hash(
            {
                "test": self._role_assignments("test"),
                "challenge": self._role_assignments("challenge"),
            }
        )

    def _load_role(
        self,
        role: Literal["train", "development", "test", "challenge"],
        service: EvaluationService,
    ) -> tuple[OptimizationCase, ...]:
        loaded = []
        for assignment in self.manifest.assignments:
            if assignment.split != role:
                continue
            case = self._loader(assignment)
            if case.case.id != assignment.case_id or case.split != assignment.split:
                raise IntegrityError("case loader output differs from immutable split assignment")
            if case.group_id != assignment.group_id:
                raise IntegrityError("case loader group differs from immutable split assignment")
            if not case.expected_response.strip():
                raise PreflightError(f"case {case.case.id!r} has no labeled expected response")
            service.preflight(case.case)
            loaded.append(case)
        return tuple(loaded)

    def _role_assignments(
        self, role: Literal["train", "development", "test", "challenge"]
    ) -> tuple[SplitAssignment, ...]:
        return tuple(item for item in self.manifest.assignments if item.split == role)

    def _role_manifest_hash(
        self, role: Literal["train", "development", "test", "challenge"]
    ) -> str:
        return content_hash({role: self._role_assignments(role)})


@dataclass(frozen=True)
class OptimizationLock:
    schema_version: int
    id: str
    base_program_hash: str
    optimizer_profile_hash: str
    split_manifest_hash: str
    train_manifest_hash: str
    development_manifest_hash: str
    held_out_assignment_hash: str
    metric_evaluators: tuple[str, ...]
    provider_id: str
    dspy_version: str
    seed: int
    content_hash: str

    @classmethod
    def create(
        cls,
        *,
        base_program: ProgramSpecification,
        profile: OptimizerProfile,
        split_manifest: SplitManifest,
        dataset: OptimizerDatasetView,
        held_out_assignment_hash: str,
        provider_id: str,
        seed: int,
    ) -> OptimizationLock:
        evaluators = tuple(
            sorted(
                {
                    f"{item.case.evaluator.name}:{item.case.evaluator.method}"
                    for item in dataset.train + dataset.development
                }
            )
        )
        identity = {
            "schema_version": 1,
            "id": f"optimization-{base_program.id}-{profile.id}",
            "base_program_hash": base_program.content_hash,
            "optimizer_profile_hash": content_hash(profile),
            "split_manifest_hash": split_manifest.content_hash,
            "train_manifest_hash": dataset.train_manifest_hash,
            "development_manifest_hash": dataset.development_manifest_hash,
            "held_out_assignment_hash": held_out_assignment_hash,
            "metric_evaluators": evaluators,
            "provider_id": provider_id,
            "dspy_version": str(dspy.__version__),
            "seed": seed,
        }
        return cls(**identity, content_hash=content_hash(identity))


@dataclass(frozen=True)
class CompiledCandidate:
    program: dspy.Module
    lock: OptimizationLock
    manifest: CompiledProgramManifest
    lock_artifact: ArtifactReference
    manifest_artifact: ArtifactReference
    budget: BudgetSnapshot
    compile_process_id: int


@dataclass(frozen=True)
class CaseComparison:
    case_id: str
    split: str
    base_score: float
    candidate_score: float
    base_evaluation: ArtifactReference
    candidate_evaluation: ArtifactReference


@dataclass(frozen=True)
class HeldOutComparison:
    compiled_manifest_hash: str
    held_out_manifest_hash: str
    base_mean: float
    candidate_mean: float
    regressions: tuple[str, ...]
    challenge_count: int
    eligible: bool
    cases: tuple[CaseComparison, ...]
    artifact: ArtifactReference


@dataclass(frozen=True)
class PromotionRecord:
    compiled_manifest_hash: str
    comparison_artifact: str
    promoted: bool
    reason: str
    artifact: ArtifactReference


Predictor = Callable[[dspy.Module, OptimizationCase, BudgetLedger], str]


class GovernedDspyOptimizer:
    def __init__(self, artifacts: ArtifactStore) -> None:
        self.artifacts = artifacts

    def compile_labeled_few_shot(
        self,
        *,
        base_program: dspy.Module,
        specification: ProgramSpecification,
        profile: OptimizerProfile,
        protected_dataset: ProtectedSplitDataset,
        evaluation_service: EvaluationService,
        provider_id: str,
        ledger: BudgetLedger,
        seed: int = 0,
    ) -> CompiledCandidate:
        if profile.engine != "dspy" or profile.optimizer != "LabeledFewShot":
            raise ConfigurationError("this compiler requires DSPy LabeledFewShot")
        if specification.engine != "dspy":
            raise ConfigurationError("optimization base program must use engine: dspy")
        dataset = protected_dataset.optimizer_view(evaluation_service)
        lock = OptimizationLock.create(
            base_program=specification,
            profile=profile,
            split_manifest=protected_dataset.manifest,
            dataset=dataset,
            held_out_assignment_hash=protected_dataset.held_out_assignment_hash,
            provider_id=provider_id,
            seed=seed,
        )
        lock_artifact = self._json_blob(lock)
        ledger.check()
        raw_k = profile.parameters.get("k", 2)
        if not isinstance(raw_k, int) or isinstance(raw_k, bool) or raw_k < 1:
            raise ConfigurationError("LabeledFewShot parameter k must be a positive integer")
        before = program_state(base_program)
        compiled, state_artifact, worker_pid = self._compile_in_subprocess(
            base_program=base_program,
            dataset=dataset,
            k=raw_k,
            timeout_seconds=float(profile.budgets["wall_seconds"]),
        )
        if program_state(base_program) != before:
            raise IntegrityError("DSPy optimizer mutated the base program")
        manifest = CompiledProgramManifest.create(
            id=f"compiled-{specification.id}-{lock.content_hash[-12:]}",
            base_program_hash=specification.content_hash,
            engine_version=str(dspy.__version__),
            optimizer_lock_hash=lock.content_hash,
            state_artifact=state_artifact.content_id,
        )
        manifest_artifact = self._json_blob(manifest)
        return CompiledCandidate(
            compiled,
            lock,
            manifest,
            lock_artifact,
            manifest_artifact,
            ledger.snapshot(),
            worker_pid,
        )

    def compare_held_out(
        self,
        *,
        base_program: dspy.Module,
        candidate: CompiledCandidate,
        protected_dataset: ProtectedSplitDataset,
        evaluation_service: EvaluationService,
        predictor: Predictor,
        ledger: BudgetLedger,
        minimum_delta: float = 0.0,
        require_no_regressions: bool = True,
        require_challenge: bool = True,
    ) -> HeldOutComparison:
        held_out = protected_dataset.held_out_after_compile(
            candidate.manifest, evaluation_service
        )
        comparisons = []
        for item in held_out.cases:
            base = evaluation_service.evaluate(
                item.case, predictor(base_program, item, ledger)
            )
            optimized = evaluation_service.evaluate(
                item.case, predictor(candidate.program, item, ledger)
            )
            self._require_score(base)
            self._require_score(optimized)
            comparisons.append(
                CaseComparison(
                    item.case.id,
                    item.split,
                    float(base.score),
                    float(optimized.score),
                    self._json_blob(base),
                    self._json_blob(optimized),
                )
            )
        base_mean = sum(item.base_score for item in comparisons) / len(comparisons)
        candidate_mean = sum(item.candidate_score for item in comparisons) / len(comparisons)
        regressions = tuple(
            item.case_id
            for item in comparisons
            if item.candidate_score + 1e-12 < item.base_score
        )
        challenge_count = sum(item.split == "challenge" for item in comparisons)
        eligible = (
            candidate_mean >= base_mean + minimum_delta
            and (not require_no_regressions or not regressions)
            and (not require_challenge or challenge_count > 0)
        )
        payload = {
            "schema_version": 1,
            "compiled_manifest_hash": candidate.manifest.content_hash,
            "held_out_manifest_hash": held_out.manifest_hash,
            "base_mean": base_mean,
            "candidate_mean": candidate_mean,
            "minimum_delta": minimum_delta,
            "regressions": regressions,
            "challenge_count": challenge_count,
            "eligible": eligible,
            "cases": comparisons,
            "budget": ledger.snapshot(),
        }
        artifact = self._json_blob(payload)
        return HeldOutComparison(
            candidate.manifest.content_hash,
            held_out.manifest_hash,
            base_mean,
            candidate_mean,
            regressions,
            challenge_count,
            eligible,
            tuple(comparisons),
            artifact,
        )

    def promote(
        self, comparison: HeldOutComparison, *, approved: bool
    ) -> PromotionRecord:
        promoted = approved and comparison.eligible
        reason = (
            "explicitly approved after held-out gate"
            if promoted
            else "not approved" if not approved else "held-out gate failed"
        )
        payload = {
            "schema_version": 1,
            "compiled_manifest_hash": comparison.compiled_manifest_hash,
            "comparison_artifact": comparison.artifact.content_id,
            "promoted": promoted,
            "reason": reason,
        }
        artifact = self._json_blob(payload)
        return PromotionRecord(
            comparison.compiled_manifest_hash,
            comparison.artifact.content_id,
            promoted,
            reason,
            artifact,
        )

    def _state_blob(self, program: dspy.Module) -> ArtifactReference:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "compiled-state.json"
            save_state_json(program, path)
            with path.open("rb") as handle:
                return self.artifacts.put_blob(handle, "application/json")

    def _compile_in_subprocess(
        self,
        *,
        base_program: dspy.Module,
        dataset: OptimizerDatasetView,
        k: int,
        timeout_seconds: float,
    ) -> tuple[dspy.Module, ArtifactReference, int]:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            base_path = temporary / "base.json"
            base_state = save_state_json(base_program, base_path)
            request = {
                "schema_version": 1,
                "base_state": base_state,
                "k": k,
                "train": [self._example_payload(item) for item in dataset.train],
                "development": [
                    self._example_payload(item) for item in dataset.development
                ],
            }
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONNOUSERSITE": "1",
            }
            if value := os.environ.get("PYTHONPATH"):
                environment["PYTHONPATH"] = os.pathsep.join(
                    str(Path(entry).resolve())
                    for entry in value.split(os.pathsep)
                    if entry
                )
            try:
                process = subprocess.run(  # noqa: S603
                    [sys.executable, "-m", "ms_agent_eval.programs.dspy.compile_worker"],
                    input=canonical_json_bytes(request),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=temporary,
                    env=environment,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as error:
                raise TimeoutError("DSPy compile worker exceeded wall-time budget") from error
            if process.returncode != 0:
                raise IntegrityError(
                    "DSPy compile worker failed: "
                    + process.stderr.decode("utf-8", errors="replace")[-1000:]
                )
            response = json.loads(process.stdout)
            if not isinstance(response, dict) or response.get("schema_version") != 1:
                raise IntegrityError("DSPy compile worker returned an invalid response")
            if response.get("development_case_count") != len(dataset.development):
                raise IntegrityError("DSPy compile worker omitted development data")
            compiled_state = response.get("compiled_state")
            if not isinstance(compiled_state, dict):
                raise IntegrityError("DSPy compile worker returned no JSON state")
            state_bytes = canonical_json_bytes(compiled_state)
            state_artifact = self.artifacts.put_blob(
                BytesIO(state_bytes), "application/json"
            )
            state_path = temporary / "compiled.json"
            state_path.write_bytes(state_bytes)
            compiled = create_program()
            load_state_json(compiled, state_path)
            worker_pid = response.get("worker_pid")
            if not isinstance(worker_pid, int):
                raise IntegrityError("DSPy compile worker returned no process identity")
            return compiled, state_artifact, worker_pid

    @staticmethod
    def _example_payload(item: OptimizationCase) -> dict[str, str]:
        return {
            "global_context": item.global_context,
            "instruction_context": item.instruction_context,
            "task": item.task,
            "response": item.expected_response,
        }

    def _json_blob(self, value: object) -> ArtifactReference:
        return self.artifacts.put_blob(
            BytesIO(canonical_json_bytes(json_value(value))), "application/json"
        )

    @staticmethod
    def _require_score(result: EvaluationRecord) -> None:
        if result.status is not EvaluationStatus.EVALUATED or result.score is None:
            raise IntegrityError(
                f"held-out evaluator returned {result.status.value}; comparison aborted"
            )
