from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from ms_agent_eval.core.config import ConfigurationRepository
from ms_agent_eval.core.errors import ConfigurationError, IntegrityError
from ms_agent_eval.core.lifecycle import ExperimentRunRecord, plan_resume
from ms_agent_eval.core.models import RunStatus
from ms_agent_eval.core.planning import plan_experiment
from ms_agent_eval.core.storage import FilesystemArtifactStore, SQLiteMetadataStore


FIXTURE = Path(__file__).parent / "fixtures" / "workspace" / "workspace.yaml"


def _lock():  # type: ignore[no-untyped-def]
    return plan_experiment(ConfigurationRepository.from_file(FIXTURE), "two-targets")


def test_content_addressed_blob_is_idempotent_and_verified(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "external")
    first = store.put_blob(BytesIO(b"same bytes"), "text/plain")
    second = store.put_blob(BytesIO(b"same bytes"), "text/plain")
    assert first == second
    assert store.verify(first)
    with store.get_blob(first) as handle:
        assert handle.read() == b"same bytes"


def test_blob_verification_detects_tampering(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "external")
    reference = store.put_blob(BytesIO(b"original"), "application/octet-stream")
    (store.data_root / reference.relative_path).write_bytes(b"changed!")
    assert not store.verify(reference)
    with pytest.raises(IntegrityError, match="failed verification"):
        store.get_blob(reference)


def test_manifest_keys_are_immutable_and_traversal_free(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "external")
    reference = store.put_manifest("experiments/run-1/lock", {"schema_version": 1})
    assert store.verify(reference)
    assert store.put_manifest("experiments/run-1/lock", {"schema_version": 1}) == reference
    with pytest.raises(IntegrityError, match="other data"):
        store.put_manifest("experiments/run-1/lock", {"schema_version": 2})
    with pytest.raises(ConfigurationError, match="safe relative"):
        store.put_manifest("../escape", {"unsafe": True})


def test_sqlite_run_creation_and_transitions_are_transactional(tmp_path: Path) -> None:
    lock = _lock()
    record = ExperimentRunRecord.create(lock)
    metadata = SQLiteMetadataStore(tmp_path / "external" / "metadata.sqlite3")
    metadata.create_experiment_run(record, lock)
    states = metadata.load_job_states(record.id)
    first = states[lock.jobs[0].id]
    running = metadata.transition_job(
        record.id,
        first.job_id,
        expected_status=RunStatus.PLANNED,
        expected_version=0,
        target_status=RunStatus.RUNNING,
    )
    completed = metadata.transition_job(
        record.id,
        first.job_id,
        expected_status=RunStatus.RUNNING,
        expected_version=running.version,
        target_status=RunStatus.COMPLETED,
    )
    assert completed.status is RunStatus.COMPLETED
    resume = plan_resume(lock, metadata.load_job_states(record.id))
    assert resume.executable_job_ids == (lock.jobs[1].id,)


def test_sqlite_compare_and_swap_rejects_stale_transition(tmp_path: Path) -> None:
    lock = _lock()
    record = ExperimentRunRecord.create(lock)
    metadata = SQLiteMetadataStore(tmp_path / "external" / "metadata.sqlite3")
    metadata.create_experiment_run(record, lock)
    job = lock.jobs[0]
    metadata.transition_job(
        record.id,
        job.id,
        expected_status=RunStatus.PLANNED,
        expected_version=0,
        target_status=RunStatus.RUNNING,
    )
    with pytest.raises(IntegrityError, match="version"):
        metadata.transition_job(
            record.id,
            job.id,
            expected_status=RunStatus.RUNNING,
            expected_version=0,
            target_status=RunStatus.COMPLETED,
        )


def test_run_creation_rolls_back_on_duplicate_identity(tmp_path: Path) -> None:
    lock = _lock()
    record = ExperimentRunRecord.create(lock)
    metadata = SQLiteMetadataStore(tmp_path / "external" / "metadata.sqlite3")
    metadata.create_experiment_run(record, lock)
    with pytest.raises(IntegrityError, match="not unique"):
        metadata.create_experiment_run(record, lock)
    assert len(metadata.load_job_states(record.id)) == len(lock.jobs)


def test_artifact_record_requires_existing_job(tmp_path: Path) -> None:
    lock = _lock()
    record = ExperimentRunRecord.create(lock)
    root = tmp_path / "external"
    metadata = SQLiteMetadataStore(root / "metadata.sqlite3")
    artifacts = FilesystemArtifactStore(root)
    metadata.create_experiment_run(record, lock)
    reference = artifacts.put_blob(BytesIO(b"response"), "text/plain")
    metadata.record_artifact(record.id, lock.jobs[0].id, "response", reference)
    assert tuple(metadata.artifacts(record.id, lock.jobs[0].id)) == (reference,)
    with pytest.raises(IntegrityError, match="unknown job"):
        metadata.record_artifact(record.id, "missing", "response", reference)


def test_storage_rejects_workspace_local_data_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with pytest.raises(ConfigurationError, match="outside"):
        FilesystemArtifactStore(workspace / "var", workspace_root=workspace)
