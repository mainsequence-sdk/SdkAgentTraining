from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.errors import IntegrityError
from ms_agent_eval.core.lifecycle import ExperimentRunRecord, JobState, ResumeAction, plan_resume
from ms_agent_eval.core.models import RunStatus
from ms_agent_eval.core.planning import plan_experiment


FIXTURE = Path(__file__).parent / "fixtures" / "workspace" / "workspace.yaml"
NOW = datetime(2026, 8, 19, tzinfo=UTC)


def _lock():  # type: ignore[no-untyped-def]
    return plan_experiment(ConfigurationRepository.from_file(FIXTURE), "two-targets")


def test_run_ids_are_collision_resistant_and_bound_to_lock() -> None:
    lock = _lock()
    first = ExperimentRunRecord.create(lock, now=NOW)
    second = ExperimentRunRecord.create(lock, now=NOW)
    assert first.id != second.id
    assert first.experiment_lock_hash == lock.content_hash


def test_job_transition_is_compare_and_swap_friendly() -> None:
    job = _lock().jobs[0]
    state = JobState.planned(
        run_id="run-example", job_id=job.id, job_hash=job.content_hash, now=NOW
    )
    running = state.transition(expected=RunStatus.PLANNED, target=RunStatus.RUNNING, now=NOW)
    completed = running.transition(
        expected=RunStatus.RUNNING, target=RunStatus.COMPLETED, now=NOW
    )
    assert (completed.status, completed.attempt, completed.version) == (
        RunStatus.COMPLETED,
        1,
        2,
    )
    with pytest.raises(IntegrityError, match="expected"):
        completed.transition(expected=RunStatus.RUNNING, target=RunStatus.FAILED, now=NOW)


def test_resume_skips_completed_and_executes_only_missing_jobs() -> None:
    lock = _lock()
    job = lock.jobs[0]
    state = JobState.planned(
        run_id="run-example", job_id=job.id, job_hash=job.content_hash, now=NOW
    )
    state = state.transition(expected=RunStatus.PLANNED, target=RunStatus.RUNNING, now=NOW)
    state = state.transition(expected=RunStatus.RUNNING, target=RunStatus.COMPLETED, now=NOW)
    resume = plan_resume(lock, {job.id: state})
    assert [decision.action for decision in resume.decisions] == [
        ResumeAction.SKIP,
        ResumeAction.EXECUTE,
    ]
    assert resume.executable_job_ids == (lock.jobs[1].id,)


def test_resume_rejects_state_from_a_different_job_identity() -> None:
    lock = _lock()
    job = lock.jobs[0]
    state = JobState.planned(
        run_id="run-example", job_id=job.id, job_hash="sha256:wrong", now=NOW
    )
    with pytest.raises(IntegrityError, match="hash mismatch"):
        plan_resume(lock, {job.id: state})


def test_running_jobs_require_explicit_reclamation() -> None:
    lock = _lock()
    job = lock.jobs[0]
    state = JobState.planned(
        run_id="run-example", job_id=job.id, job_hash=job.content_hash, now=NOW
    ).transition(expected=RunStatus.PLANNED, target=RunStatus.RUNNING, now=NOW)
    assert plan_resume(lock, {job.id: state}).decisions[0].action is ResumeAction.BLOCKED
    assert (
        plan_resume(lock, {job.id: state}, reclaim_running=True).decisions[0].action
        is ResumeAction.EXECUTE
    )
