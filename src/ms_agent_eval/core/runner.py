from __future__ import annotations

from dataclasses import dataclass

from .evaluation import CaseDefinition, EvaluationRecord, EvaluationService
from .errors import IntegrityError
from .hashing import json_value
from .lifecycle import JobState
from .models import (
    ArtifactReference,
    PlannedJob,
    ProgramResult,
    ProgramSpecification,
    RunStatus,
)
from .programs import ProgramEngine, ProgramInputs
from .providers import ModelCallObserver, ModelProvider
from .storage import FilesystemArtifactStore, SQLiteMetadataStore


@dataclass(frozen=True)
class JobExecution:
    job: PlannedJob
    program: ProgramSpecification
    inputs: ProgramInputs


@dataclass(frozen=True)
class EvaluatedJobResult:
    program_result: ProgramResult
    evaluation: EvaluationRecord | None
    evaluation_artifact: ArtifactReference | None


class ExperimentRunner:
    """Target-neutral lifecycle wrapper around a selected program engine/provider."""

    def __init__(
        self,
        *,
        artifacts: FilesystemArtifactStore,
        metadata: SQLiteMetadataStore,
    ) -> None:
        self.artifacts = artifacts
        self.metadata = metadata

    def execute(
        self,
        *,
        run_id: str,
        execution: JobExecution,
        engine: ProgramEngine,
        provider: ModelProvider,
    ) -> ProgramResult:
        if execution.program.engine != engine.id:
            raise IntegrityError(
                f"program engine {execution.program.engine!r} does not match {engine.id!r}"
            )
        state = self._state(run_id, execution.job.id)
        running = self.metadata.transition_job(
            run_id,
            execution.job.id,
            expected_status=state.status,
            expected_version=state.version,
            target_status=RunStatus.RUNNING,
        )
        observer = ModelCallObserver(self.artifacts)
        try:
            result = engine.execute(
                specification=execution.program,
                inputs=execution.inputs,
                provider=provider,
                observer=observer,
            )
        except Exception as error:
            self._persist_failure(
                run_id, execution.job, running, type(error).__name__, str(error)
            )
            raise

        reference = self.artifacts.put_manifest(
            f"experiments/{run_id}/jobs/{execution.job.id}/result-attempt-{running.attempt}",
            {
                "schema_version": 1,
                "run_id": run_id,
                "job_id": execution.job.id,
                "job_hash": execution.job.content_hash,
                "program_hash": execution.program.content_hash,
                "provider_id": provider.id,
                "result": json_value(result),
            },
        )
        self.metadata.record_artifact(run_id, execution.job.id, "program_result", reference)
        if result.status == "completed":
            target_status = RunStatus.COMPLETED
            error_kind = None
        else:
            target_status = RunStatus.FAILED
            error_kind = result.error_kind or "program_failed"
        self.metadata.transition_job(
            run_id,
            execution.job.id,
            expected_status=RunStatus.RUNNING,
            expected_version=running.version,
            target_status=target_status,
            error_kind=error_kind,
        )
        return result

    def execute_evaluated(
        self,
        *,
        run_id: str,
        execution: JobExecution,
        engine: ProgramEngine,
        provider: ModelProvider,
        case: CaseDefinition,
        evaluation_service: EvaluationService,
        allow_unscored: bool = False,
    ) -> EvaluatedJobResult:
        """Generate and evaluate with fail-closed preflight before the model call."""

        evaluation_service.preflight(case, allow_unscored=allow_unscored)
        result = self.execute(
            run_id=run_id,
            execution=execution,
            engine=engine,
            provider=provider,
        )
        if result.status != "completed" or result.primary_response is None:
            return EvaluatedJobResult(result, None, None)
        evaluation = evaluation_service.evaluate(
            case,
            result.primary_response,
            allow_unscored=allow_unscored,
        )
        attempt = self.metadata.load_job_states(run_id)[execution.job.id].attempt
        reference = self.artifacts.put_manifest(
            f"experiments/{run_id}/jobs/{execution.job.id}/evaluation-attempt-{attempt}",
            {
                "schema_version": 1,
                "run_id": run_id,
                "job_id": execution.job.id,
                "job_hash": execution.job.content_hash,
                "evaluation": json_value(evaluation),
            },
        )
        self.metadata.record_artifact(run_id, execution.job.id, "evaluation", reference)
        return EvaluatedJobResult(result, evaluation, reference)

    def _state(self, run_id: str, job_id: str) -> JobState:
        state = self.metadata.load_job_states(run_id).get(job_id)
        if state is None:
            raise IntegrityError(f"job {job_id!r} is absent from run {run_id!r}")
        if state.status not in {RunStatus.PLANNED, RunStatus.FAILED}:
            raise IntegrityError(
                f"job {job_id!r} cannot execute from status {state.status.value!r}"
            )
        return state

    def _persist_failure(
        self,
        run_id: str,
        job: PlannedJob,
        running: JobState,
        error_kind: str,
        message: str,
    ) -> None:
        reference = self.artifacts.put_manifest(
            f"experiments/{run_id}/jobs/{job.id}/failure-attempt-{running.attempt}",
            {
                "schema_version": 1,
                "run_id": run_id,
                "job_id": job.id,
                "job_hash": job.content_hash,
                "error_kind": error_kind,
                "message": message,
            },
        )
        self.metadata.record_artifact(run_id, job.id, "program_failure", reference)
        self.metadata.transition_job(
            run_id,
            job.id,
            expected_status=RunStatus.RUNNING,
            expected_version=running.version,
            target_status=RunStatus.FAILED,
            error_kind=error_kind,
        )
