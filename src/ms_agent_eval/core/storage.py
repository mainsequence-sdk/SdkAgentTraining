from __future__ import annotations

import hashlib
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol

from .errors import ConfigurationError, IntegrityError, ResolutionError
from .hashing import canonical_json_bytes, sha256_file
from .lifecycle import ExperimentRunRecord, JobState
from .models import ArtifactReference, ExperimentLock, RunStatus


def validate_external_data_root(data_root: Path, *, workspace_root: Path | None = None) -> Path:
    resolved = data_root.resolve()
    if workspace_root is not None:
        workspace = workspace_root.resolve()
        if resolved == workspace or workspace in resolved.parents:
            raise ConfigurationError("runtime artifact storage must be outside the Git workspace")
    return resolved


class ArtifactStore(Protocol):
    def put_blob(self, content: BinaryIO, media_type: str) -> ArtifactReference: ...

    def get_blob(self, reference: ArtifactReference) -> BinaryIO: ...

    def put_manifest(
        self, key: str, document: Mapping[str, object]
    ) -> ArtifactReference: ...

    def verify(self, reference: ArtifactReference) -> bool: ...


class MetadataStore(Protocol):
    def create_experiment_run(
        self, record: ExperimentRunRecord, lock: ExperimentLock
    ) -> None: ...

    def transition_job(
        self,
        run_id: str,
        job_id: str,
        *,
        expected_status: RunStatus,
        expected_version: int,
        target_status: RunStatus,
        error_kind: str | None = None,
    ) -> JobState: ...

    def load_job_states(self, run_id: str) -> Mapping[str, JobState]: ...


def _safe_manifest_key(key: str) -> str:
    path = PurePosixPath(key)
    if (
        not key
        or path.is_absolute()
        or ".." in path.parts
        or "\x00" in key
        or ":" in path.parts[0]
    ):
        raise ConfigurationError("manifest key must be a safe relative POSIX path")
    return path.as_posix().removesuffix(".json")


class FilesystemArtifactStore:
    def __init__(self, data_root: Path, *, workspace_root: Path | None = None) -> None:
        self.data_root = validate_external_data_root(
            data_root, workspace_root=workspace_root
        )
        self.blob_root = self.data_root / "blobs" / "sha256"
        self.manifest_root = self.data_root / "manifests"
        self.temporary_root = self.data_root / "tmp"
        for directory in (self.blob_root, self.manifest_root, self.temporary_root):
            directory.mkdir(parents=True, exist_ok=True)

    def put_blob(self, content: BinaryIO, media_type: str) -> ArtifactReference:
        if not media_type.strip():
            raise ConfigurationError("artifact media type must not be empty")
        descriptor, temporary_name = tempfile.mkstemp(prefix="blob-", dir=self.temporary_root)
        digest = hashlib.sha256()
        size = 0
        try:
            with os.fdopen(descriptor, "wb") as handle:
                while chunk := content.read(1024 * 1024):
                    digest.update(chunk)
                    size += len(chunk)
                    handle.write(chunk)
                handle.flush()
                os.fsync(handle.fileno())
            hex_digest = digest.hexdigest()
            destination = self.blob_root / hex_digest
            if destination.exists():
                os.unlink(temporary_name)
            else:
                os.replace(temporary_name, destination)
            reference = ArtifactReference(
                content_id=f"sha256:{hex_digest}",
                media_type=media_type,
                size_bytes=size,
                relative_path=destination.relative_to(self.data_root).as_posix(),
            )
            if not self.verify(reference):
                raise IntegrityError("content-addressed blob failed verification after publication")
            return reference
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise

    def get_blob(self, reference: ArtifactReference) -> BinaryIO:
        if not self.verify(reference):
            raise IntegrityError(f"artifact failed verification: {reference.content_id}")
        return (self.data_root / reference.relative_path).open("rb")

    def put_manifest(
        self, key: str, document: Mapping[str, object]
    ) -> ArtifactReference:
        safe_key = _safe_manifest_key(key)
        payload = canonical_json_bytes(document)
        digest = hashlib.sha256(payload).hexdigest()
        destination = self.manifest_root / f"{safe_key}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != payload:
                raise IntegrityError(f"immutable manifest key already contains other data: {key}")
        else:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
            )
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary_name, destination)
            except BaseException:
                try:
                    os.unlink(temporary_name)
                except FileNotFoundError:
                    pass
                raise
        reference = ArtifactReference(
            content_id=f"sha256:{digest}",
            media_type="application/json",
            size_bytes=len(payload),
            relative_path=destination.relative_to(self.data_root).as_posix(),
        )
        if not self.verify(reference):
            raise IntegrityError("manifest failed verification after publication")
        return reference

    def verify(self, reference: ArtifactReference) -> bool:
        relative = PurePosixPath(reference.relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            return False
        path = self.data_root / relative.as_posix()
        if path.is_symlink() or not path.is_file():
            return False
        return (
            path.stat().st_size == reference.size_bytes
            and sha256_file(path) == reference.content_id
        )


class SQLiteMetadataStore:
    def __init__(self, database_path: Path, *, workspace_root: Path | None = None) -> None:
        self.database_path = database_path.resolve()
        validate_external_data_root(
            self.database_path.parent, workspace_root=workspace_root
        )
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    @contextmanager
    def _managed_connection(self):  # type: ignore[no-untyped-def]
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._managed_connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS experiment_runs (
                    id TEXT PRIMARY KEY,
                    experiment_lock_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    run_id TEXT NOT NULL REFERENCES experiment_runs(id),
                    job_id TEXT NOT NULL,
                    job_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    error_kind TEXT,
                    PRIMARY KEY (run_id, job_id)
                );
                CREATE TABLE IF NOT EXISTS job_artifacts (
                    run_id TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    relative_path TEXT NOT NULL,
                    PRIMARY KEY (run_id, job_id, kind, content_id),
                    FOREIGN KEY (run_id, job_id) REFERENCES jobs(run_id, job_id)
                );
                CREATE INDEX IF NOT EXISTS jobs_status_index ON jobs(run_id, status);
                """
            )

    def create_experiment_run(
        self, record: ExperimentRunRecord, lock: ExperimentLock
    ) -> None:
        if record.experiment_lock_hash != lock.content_hash:
            raise IntegrityError("experiment run and lock hashes differ")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "INSERT INTO experiment_runs VALUES (?, ?, ?)",
                (record.id, record.experiment_lock_hash, record.created_at),
            )
            for job in lock.jobs:
                state = JobState.planned(
                    run_id=record.id, job_id=job.id, job_hash=job.content_hash
                )
                connection.execute(
                    "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        state.run_id,
                        state.job_id,
                        state.job_hash,
                        state.status.value,
                        state.attempt,
                        state.version,
                        state.updated_at,
                        state.error_kind,
                    ),
                )
            connection.commit()
        except sqlite3.IntegrityError as error:
            connection.rollback()
            raise IntegrityError(f"experiment run creation was not unique: {record.id}") from error
        finally:
            connection.close()

    def transition_job(
        self,
        run_id: str,
        job_id: str,
        *,
        expected_status: RunStatus,
        expected_version: int,
        target_status: RunStatus,
        error_kind: str | None = None,
    ) -> JobState:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE run_id = ? AND job_id = ?",
                (run_id, job_id),
            ).fetchone()
            if row is None:
                raise ResolutionError(f"unknown run/job pair: {run_id}/{job_id}")
            current = self._state(row)
            if current.version != expected_version:
                raise IntegrityError(
                    f"job {job_id!r} version is {current.version}, expected {expected_version}"
                )
            target = current.transition(
                expected=expected_status,
                target=target_status,
                error_kind=error_kind,
            )
            cursor = connection.execute(
                """
                UPDATE jobs
                SET status = ?, attempt = ?, version = ?, updated_at = ?, error_kind = ?
                WHERE run_id = ? AND job_id = ? AND status = ? AND version = ?
                """,
                (
                    target.status.value,
                    target.attempt,
                    target.version,
                    target.updated_at,
                    target.error_kind,
                    run_id,
                    job_id,
                    expected_status.value,
                    expected_version,
                ),
            )
            if cursor.rowcount != 1:
                raise IntegrityError(f"concurrent transition detected for job {job_id!r}")
            connection.commit()
            return target
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def load_job_states(self, run_id: str) -> Mapping[str, JobState]:
        with self._managed_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE run_id = ? ORDER BY job_id", (run_id,)
            ).fetchall()
        if not rows:
            raise ResolutionError(f"experiment run has no jobs or does not exist: {run_id}")
        return {row["job_id"]: self._state(row) for row in rows}

    def record_artifact(
        self,
        run_id: str,
        job_id: str,
        kind: str,
        reference: ArtifactReference,
    ) -> None:
        if not kind.strip():
            raise ConfigurationError("artifact kind must not be empty")
        try:
            with self._managed_connection() as connection:
                connection.execute(
                    "INSERT INTO job_artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        job_id,
                        kind,
                        reference.content_id,
                        reference.media_type,
                        reference.size_bytes,
                        reference.relative_path,
                    ),
                )
        except sqlite3.IntegrityError as error:
            raise IntegrityError("artifact record is duplicate or references an unknown job") from error

    def artifacts(self, run_id: str, job_id: str) -> Iterable[ArtifactReference]:
        with self._managed_connection() as connection:
            rows = connection.execute(
                """
                SELECT content_id, media_type, size_bytes, relative_path
                FROM job_artifacts WHERE run_id = ? AND job_id = ?
                ORDER BY kind, content_id
                """,
                (run_id, job_id),
            ).fetchall()
        return tuple(
            ArtifactReference(
                content_id=row["content_id"],
                media_type=row["media_type"],
                size_bytes=row["size_bytes"],
                relative_path=row["relative_path"],
            )
            for row in rows
        )

    @staticmethod
    def _state(row: sqlite3.Row) -> JobState:
        return JobState(
            run_id=row["run_id"],
            job_id=row["job_id"],
            job_hash=row["job_hash"],
            status=RunStatus(row["status"]),
            attempt=row["attempt"],
            version=row["version"],
            updated_at=row["updated_at"],
            error_kind=row["error_kind"],
        )
