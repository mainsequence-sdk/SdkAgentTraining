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
from .models import ArtifactReference, RuntimeProfile
from .storage import FilesystemArtifactStore


_IMAGE_PATTERN = re.compile(r"^[^\s]+@sha256:[0-9a-f]{64}$")
_ENVIRONMENT_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class ExecutionRole(str, Enum):
    TARGET = "target"
    TRUSTED_EVALUATOR = "trusted_evaluator"


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
    def run(
        self,
        arguments: Sequence[str],
        *,
        timeout_seconds: int,
        container_name: str,
        maximum_capture_bytes: int,
    ) -> ProcessOutcome: ...

    def preflight(self) -> None: ...


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
        stdout_file = tempfile.TemporaryFile()
        stderr_file = tempfile.TemporaryFile()
        try:
            process = subprocess.Popen(
                list(arguments),
                stdout=stdout_file,
                stderr=stderr_file,
            )
            timed_out = False
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = None
                subprocess.run(
                    ["docker", "rm", "--force", container_name],
                    check=False,
                    capture_output=True,
                    timeout=30,
                )
                process.kill()
                process.wait(timeout=30)
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout = stdout_file.read(maximum_capture_bytes + 1)
            stderr = stderr_file.read(maximum_capture_bytes + 1)
            truncated = (
                len(stdout) > maximum_capture_bytes or len(stderr) > maximum_capture_bytes
            )
            return ProcessOutcome(
                exit_code,
                stdout[:maximum_capture_bytes],
                stderr[:maximum_capture_bytes],
                timed_out,
                truncated,
            )
        except OSError as error:
            raise PreflightError("Docker executable could not be started") from error
        finally:
            stdout_file.close()
            stderr_file.close()


@dataclass(frozen=True)
class ExecutionRequest:
    id: str
    role: ExecutionRole
    repository_directory: Path
    command: tuple[str, ...]
    runtime: RuntimeProfile
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


class ExecutionBackend(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class DockerExecutor:
    def __init__(
        self,
        artifact_store: FilesystemArtifactStore,
        runner: ContainerRunner | None = None,
    ) -> None:
        self.artifact_store = artifact_store
        self.runner = runner or SubprocessDockerRunner()

    def preflight(self, runtime: RuntimeProfile) -> None:
        if runtime.backend != "docker" or not runtime.image:
            raise PreflightError("Docker executor requires a Docker runtime profile")
        if not _IMAGE_PATTERN.fullmatch(runtime.image):
            raise PreflightError("Docker image is not pinned by digest")
        if runtime.network != "none":
            raise PreflightError("the initial isolated executor supports only network: none")
        self.runner.preflight()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.preflight(request.runtime)
        if not request.command or any("\x00" in argument for argument in request.command):
            raise ConfigurationError("container command must be a non-empty NUL-free argv")
        invalid_environment = sorted(
            name for name in request.environment if not _ENVIRONMENT_PATTERN.fullmatch(name)
        )
        if invalid_environment:
            raise ConfigurationError(
                f"invalid container environment variable names: {invalid_environment}"
            )
        if any("\n" in value or "\r" in value or "\x00" in value for value in request.environment.values()):
            raise ConfigurationError("container environment values must be single-line and NUL-free")
        self._validate_input_tree(request.repository_directory)

        staging = Path(
            tempfile.mkdtemp(prefix="execution-", dir=self.artifact_store.temporary_root)
        )
        name = f"ms-agent-eval-{uuid4().hex}"
        try:
            target = staging / "target"
            output = staging / "output"
            shutil.copytree(request.repository_directory, target, symlinks=False)
            output.mkdir()
            self._make_container_writable(target)
            output.chmod(0o777)
            environment_file = staging / "container.env"
            environment_file.write_text(
                "".join(f"{key}={value}\n" for key, value in request.environment.items()),
                encoding="utf-8",
            )
            environment_file.chmod(0o600)
            arguments = self._docker_arguments(
                request, name=name, target=target, output=output, environment_file=environment_file
            )
            outcome = self.runner.run(
                arguments,
                timeout_seconds=request.runtime.timeout_seconds,
                container_name=name,
                maximum_capture_bytes=request.runtime.maximum_output_bytes,
            )
            stdout = self.artifact_store.put_blob(
                _bytes_reader(outcome.stdout), "text/plain; charset=utf-8"
            )
            stderr = self.artifact_store.put_blob(
                _bytes_reader(outcome.stderr), "text/plain; charset=utf-8"
            )
            output_size = self._tree_size(output)
            output_artifact = None
            error_kind = None
            if outcome.timed_out:
                status = ExecutionStatus.TIMED_OUT
                error_kind = "execution_timeout"
            elif outcome.output_truncated or output_size > request.runtime.maximum_output_bytes:
                status = ExecutionStatus.FAILED
                error_kind = "output_limit_exceeded"
            elif outcome.exit_code == 0:
                status = ExecutionStatus.COMPLETED
            else:
                status = ExecutionStatus.FAILED
                error_kind = "nonzero_exit"
            if output_size <= request.runtime.maximum_output_bytes:
                output_artifact = self._archive_output(output, staging)
            evidence = self.artifact_store.put_manifest(
                f"executions/{request.id}/{uuid4().hex}",
                {
                    "schema_version": 1,
                    "request_id": request.id,
                    "role": request.role,
                    "image": request.runtime.image,
                    "command": request.command,
                    "network": request.runtime.network,
                    "root_filesystem_read_only": True,
                    "capabilities_dropped": ["ALL"],
                    "no_new_privileges": True,
                    "user": request.runtime.user,
                    "resources": {
                        "cpus": request.runtime.cpus,
                        "memory_mb": request.runtime.memory_mb,
                        "pids": request.runtime.pids,
                        "timeout_seconds": request.runtime.timeout_seconds,
                        "maximum_output_bytes": request.runtime.maximum_output_bytes,
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
    def _docker_arguments(
        request: ExecutionRequest,
        *,
        name: str,
        target: Path,
        output: Path,
        environment_file: Path,
    ) -> list[str]:
        runtime = request.runtime
        target_mount = f"type=bind,src={target},dst=/workspace/target"
        if request.role is ExecutionRole.TRUSTED_EVALUATOR:
            target_mount += ",readonly"
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            name,
            "--network",
            "none",
            "--cpus",
            str(runtime.cpus),
            "--memory",
            f"{runtime.memory_mb}m",
            "--pids-limit",
            str(runtime.pids),
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--user",
            runtime.user,
            "--env-file",
            str(environment_file),
            "--mount",
            target_mount,
            "--mount",
            f"type=bind,src={output},dst=/workspace/output",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--workdir",
            "/workspace/target",
            runtime.image or "",
            *request.command,
        ]

    @staticmethod
    def _validate_input_tree(root: Path) -> None:
        if root.is_symlink() or not root.is_dir():
            raise ConfigurationError("execution repository input must be a real directory")
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ConfigurationError(f"execution input contains a symlink: {path}")

    @staticmethod
    def _make_container_writable(root: Path) -> None:
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

    def _archive_output(self, output: Path, staging: Path) -> ArtifactReference:
        archive = staging / "output.tar"
        with tarfile.open(archive, "w") as handle:
            for path in sorted(output.rglob("*")):
                handle.add(path, arcname=path.relative_to(output), recursive=False)
        with archive.open("rb") as content:
            return self.artifact_store.put_blob(content, "application/x-tar")


def _bytes_reader(value: bytes):  # type: ignore[no-untyped-def]
    from io import BytesIO

    return BytesIO(value)
