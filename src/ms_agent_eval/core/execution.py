from __future__ import annotations

import re
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from .errors import ConfigurationError, PreflightError
from .models import ArtifactReference
from .storage import FilesystemArtifactStore
from .workspace import RuntimeConfiguration


_IMAGE = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
_ENVIRONMENT = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class ProcessOutcome:
    exit_code: int | None
    stdout: bytes
    stderr: bytes
    timed_out: bool
    output_truncated: bool = False


class ContainerRunner(Protocol):
    def preflight(self) -> None: ...

    def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: int,
        container_name: str,
        maximum_capture_bytes: int,
    ) -> ProcessOutcome: ...


class SubprocessDockerRunner:
    def preflight(self) -> None:
        try:
            subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PreflightError("Docker daemon is not available") from error

    def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: int,
        container_name: str,
        maximum_capture_bytes: int,
    ) -> ProcessOutcome:
        try:
            completed = subprocess.run(
                list(arguments),
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            stdout = completed.stdout
            stderr = completed.stderr
            truncated = max(len(stdout), len(stderr)) > maximum_capture_bytes
            return ProcessOutcome(
                completed.returncode,
                stdout[:maximum_capture_bytes],
                stderr[:maximum_capture_bytes],
                False,
                truncated,
            )
        except subprocess.TimeoutExpired as error:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                check=False,
                capture_output=True,
                timeout=30,
            )
            return ProcessOutcome(
                None,
                (error.stdout or b"")[:maximum_capture_bytes],
                (error.stderr or b"")[:maximum_capture_bytes],
                True,
            )
        except OSError as error:
            raise PreflightError("Docker executable could not be started") from error


@dataclass(frozen=True)
class ExecutionRequest:
    id: str
    repository_directory: Path
    command: tuple[str, ...]
    runtime: RuntimeConfiguration
    environment: Mapping[str, str]


@dataclass(frozen=True)
class ExecutionResult:
    status: ExecutionStatus
    exit_code: int | None
    error_kind: str | None
    stdout_artifact: ArtifactReference
    stderr_artifact: ArtifactReference
    output_artifact: ArtifactReference | None
    evidence_artifact: ArtifactReference


class DockerExecutor:
    """Run target-repository commands in an isolated, digest-pinned container."""

    timeout_seconds = 300
    maximum_output_bytes = 10 * 1024 * 1024

    def __init__(
        self,
        artifact_store: FilesystemArtifactStore,
        runner: ContainerRunner | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.runner = runner or SubprocessDockerRunner()

    def preflight(self, runtime: RuntimeConfiguration) -> None:
        if runtime.type != "docker" or not runtime.image:
            raise PreflightError("Docker execution requires runtime.type=docker")
        if _IMAGE.fullmatch(runtime.image) is None:
            raise PreflightError("Docker image must be pinned by sha256 digest")
        if runtime.network != "none":
            raise PreflightError("isolated target execution currently requires network: none")
        self.runner.preflight()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.preflight(request.runtime)
        if not request.command or any("\x00" in item for item in request.command):
            raise ConfigurationError("container command must be non-empty NUL-free argv")
        invalid = sorted(
            name for name in request.environment if _ENVIRONMENT.fullmatch(name) is None
        )
        if invalid:
            raise ConfigurationError(f"invalid container environment names: {invalid}")
        if any(
            any(character in value for character in ("\n", "\r", "\x00"))
            for value in request.environment.values()
        ):
            raise ConfigurationError("container environment values must be single-line")
        self._validate_tree(request.repository_directory)
        staging = Path(
            tempfile.mkdtemp(prefix="execution-", dir=self.artifact_store.temporary_root)
        )
        name = f"ms-agent-eval-{uuid4().hex}"
        try:
            target = staging / "target"
            output = staging / "output"
            shutil.copytree(request.repository_directory, target, symlinks=False)
            output.mkdir()
            self._make_writable(target)
            output.chmod(0o777)
            environment_file = staging / "container.env"
            environment_file.write_text(
                "".join(f"{key}={value}\n" for key, value in request.environment.items()),
                encoding="utf-8",
            )
            environment_file.chmod(0o600)
            outcome = self.runner.run(
                self._arguments(request, name, target, output, environment_file),
                timeout_seconds=self.timeout_seconds,
                container_name=name,
                maximum_capture_bytes=self.maximum_output_bytes,
            )
            stdout = self.artifact_store.put_blob(
                _reader(outcome.stdout), "text/plain; charset=utf-8"
            )
            stderr = self.artifact_store.put_blob(
                _reader(outcome.stderr), "text/plain; charset=utf-8"
            )
            output_size = self._tree_size(output)
            if outcome.timed_out:
                status, error_kind = ExecutionStatus.TIMED_OUT, "execution_timeout"
            elif outcome.output_truncated or output_size > self.maximum_output_bytes:
                status, error_kind = ExecutionStatus.FAILED, "output_limit_exceeded"
            elif outcome.exit_code == 0:
                status, error_kind = ExecutionStatus.COMPLETED, None
            else:
                status, error_kind = ExecutionStatus.FAILED, "nonzero_exit"
            output_artifact = (
                self._archive(output, staging) if output_size <= self.maximum_output_bytes else None
            )
            evidence = self.artifact_store.put_manifest(
                f"executions/{request.id}/{uuid4().hex}",
                {
                    "schema_version": 2,
                    "request_id": request.id,
                    "image": request.runtime.image,
                    "command": request.command,
                    "network": "none",
                    "root_filesystem_read_only": True,
                    "capabilities_dropped": ["ALL"],
                    "no_new_privileges": True,
                    "resources": {
                        "cpus": 2,
                        "memory_mb": 2048,
                        "pids": 256,
                        "timeout_seconds": self.timeout_seconds,
                        "maximum_output_bytes": self.maximum_output_bytes,
                    },
                    "environment_names": sorted(request.environment),
                    "status": status,
                    "exit_code": outcome.exit_code,
                    "error_kind": error_kind,
                    "stdout": stdout,
                    "stderr": stderr,
                    "output": output_artifact,
                },
            )
            return ExecutionResult(
                status,
                outcome.exit_code,
                error_kind,
                stdout,
                stderr,
                output_artifact,
                evidence,
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def _arguments(
        request: ExecutionRequest,
        name: str,
        target: Path,
        output: Path,
        environment_file: Path,
    ) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--cpus",
            "2",
            "--memory",
            "2048m",
            "--pids-limit",
            "256",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            "65534:65534",
            "--env-file",
            str(environment_file),
            "--mount",
            f"type=bind,src={target},dst=/workspace/target",
            "--mount",
            f"type=bind,src={output},dst=/workspace/output",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--workdir",
            "/workspace/target",
            request.runtime.image or "",
            *request.command,
        ]

    @staticmethod
    def _validate_tree(root: Path) -> None:
        if root.is_symlink() or not root.is_dir():
            raise ConfigurationError("execution input must be a real directory")
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ConfigurationError(f"execution input contains a symlink: {path}")

    @staticmethod
    def _make_writable(root: Path) -> None:
        root.chmod(0o777)
        for path in root.rglob("*"):
            path.chmod(0o777 if path.is_dir() else 0o666)

    @staticmethod
    def _tree_size(root: Path) -> int:
        size = 0
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ConfigurationError(f"container output contains a symlink: {path}")
            if path.is_file():
                size += path.stat().st_size
        return size

    def _archive(self, output: Path, staging: Path) -> ArtifactReference:
        archive = staging / "output.tar"
        with tarfile.open(archive, "w") as handle:
            for path in sorted(output.rglob("*")):
                handle.add(path, arcname=path.relative_to(output), recursive=False)
        with archive.open("rb") as content:
            return self.artifact_store.put_blob(content, "application/x-tar")


def _reader(value: bytes):  # type: ignore[no-untyped-def]
    from io import BytesIO

    return BytesIO(value)
