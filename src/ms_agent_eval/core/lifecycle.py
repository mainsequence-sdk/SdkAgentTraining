from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4

from .errors import IntegrityError
from .models import ExperimentLock, RunStatus


class ResumeAction(str, Enum):
    EXECUTE = "execute"
    SKIP = "skip"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class ExperimentRunRecord:
    id: str
    experiment_lock_hash: str
    created_at: str

    @classmethod
    def create(cls, lock: ExperimentLock, *, now: datetime | None = None) -> ExperimentRunRecord:
        timestamp = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
        return cls(
            id=f"run-{uuid4()}",
            experiment_lock_hash=lock.content_hash,
            created_at=timestamp,
        )


@dataclass(frozen=True)
class JobState:
    run_id: str
    job_id: str
    job_hash: str
    status: RunStatus
    attempt: int
    version: int
    updated_at: str
    error_kind: str | None = None

    @classmethod
    def planned(
        cls,
        *,
        run_id: str,
        job_id: str,
        job_hash: str,
        now: datetime | None = None,
    ) -> JobState:
        return cls(
            run_id=run_id,
            job_id=job_id,
            job_hash=job_hash,
            status=RunStatus.PLANNED,
            attempt=0,
            version=0,
            updated_at=(now or datetime.now(UTC)).astimezone(UTC).isoformat(),
        )

    def transition(
        self,
        *,
        expected: RunStatus,
        target: RunStatus,
        now: datetime | None = None,
        error_kind: str | None = None,
    ) -> JobState:
        if self.status is not expected:
            raise IntegrityError(
                f"job {self.job_id!r} is {self.status.value!r}, expected {expected.value!r}"
            )
        allowed = {
            RunStatus.PLANNED: {RunStatus.RUNNING},
            RunStatus.RUNNING: {
                RunStatus.COMPLETED,
                RunStatus.FAILED,
                RunStatus.BUDGET_EXHAUSTED,
            },
            RunStatus.FAILED: {RunStatus.RUNNING},
            RunStatus.COMPLETED: set(),
            RunStatus.BUDGET_EXHAUSTED: set(),
        }
        if target not in allowed[expected]:
            raise IntegrityError(
                f"invalid job transition {expected.value!r} -> {target.value!r}"
            )
        if target is RunStatus.COMPLETED and error_kind is not None:
            raise IntegrityError("completed jobs cannot retain an error kind")
        if target in {RunStatus.FAILED, RunStatus.BUDGET_EXHAUSTED} and not error_kind:
            raise IntegrityError(f"{target.value} jobs require a structured error kind")
        return replace(
            self,
            status=target,
            attempt=self.attempt + (1 if target is RunStatus.RUNNING else 0),
            version=self.version + 1,
            updated_at=(now or datetime.now(UTC)).astimezone(UTC).isoformat(),
            error_kind=error_kind,
        )


@dataclass(frozen=True)
class ResumeDecision:
    job_id: str
    action: ResumeAction
    reason: str


@dataclass(frozen=True)
class ResumePlan:
    experiment_lock_hash: str
    decisions: tuple[ResumeDecision, ...]

    @property
    def executable_job_ids(self) -> tuple[str, ...]:
        return tuple(
            decision.job_id
            for decision in self.decisions
            if decision.action is ResumeAction.EXECUTE
        )


def plan_resume(
    lock: ExperimentLock,
    states: Mapping[str, JobState],
    *,
    retry_failed: bool = True,
    reclaim_running: bool = False,
) -> ResumePlan:
    planned_ids = {job.id for job in lock.jobs}
    unknown = sorted(set(states) - planned_ids)
    if unknown:
        raise IntegrityError(f"resume state contains jobs absent from the lock: {unknown}")

    decisions: list[ResumeDecision] = []
    for job in lock.jobs:
        state = states.get(job.id)
        if state is None:
            decisions.append(ResumeDecision(job.id, ResumeAction.EXECUTE, "not_started"))
            continue
        if state.job_hash != job.content_hash:
            raise IntegrityError(f"resume state hash mismatch for job {job.id!r}")
        if state.status is RunStatus.COMPLETED:
            decisions.append(ResumeDecision(job.id, ResumeAction.SKIP, "completed"))
        elif state.status is RunStatus.BUDGET_EXHAUSTED:
            decisions.append(
                ResumeDecision(job.id, ResumeAction.BLOCKED, "budget_exhausted")
            )
        elif state.status is RunStatus.RUNNING and not reclaim_running:
            decisions.append(ResumeDecision(job.id, ResumeAction.BLOCKED, "still_running"))
        elif state.status is RunStatus.FAILED and not retry_failed:
            decisions.append(ResumeDecision(job.id, ResumeAction.BLOCKED, "failed"))
        else:
            reason = "reclaim_running" if state.status is RunStatus.RUNNING else "retryable"
            decisions.append(ResumeDecision(job.id, ResumeAction.EXECUTE, reason))
    return ResumePlan(lock.content_hash, tuple(decisions))
