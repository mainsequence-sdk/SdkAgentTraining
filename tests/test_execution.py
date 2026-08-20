from __future__ import annotations

import json
import os
import tarfile
from pathlib import Path

import pytest
import yaml

from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.execution import (
    DockerExecutor,
    ExecutionRequest,
    ExecutionRole,
    ExecutionStatus,
    ProcessOutcome,
)
from ms_agent_eval.core.models import RuntimeProfile
from ms_agent_eval.core.storage import FilesystemArtifactStore


ROOT = Path(__file__).parents[1]
RUNTIME_FILE = ROOT / "tests" / "fixtures" / "runtime" / "python-uv-3.12.yaml"


def _runtime() -> RuntimeProfile:
    return RuntimeProfile.from_mapping(yaml.safe_load(RUNTIME_FILE.read_text(encoding="utf-8")))


class FakeRunner:
    def __init__(self, outcome: ProcessOutcome | None = None) -> None:
        self.outcome = outcome or ProcessOutcome(0, b"standard output", b"", False)
        self.arguments: list[str] | None = None
        self.preflight_called = False

    def preflight(self) -> None:
        self.preflight_called = True

    def run(  # type: ignore[no-untyped-def]
        self, arguments, *, timeout_seconds, container_name, maximum_capture_bytes
    ):
        self.arguments = list(arguments)
        for index, argument in enumerate(arguments):
            if argument == "--mount" and "dst=/workspace/output" in arguments[index + 1]:
                source = arguments[index + 1].split("src=", 1)[1].split(",dst=", 1)[0]
                (Path(source) / "evidence.json").write_text("{}\n", encoding="utf-8")
        return self.outcome


def _request(repository: Path, *, role: ExecutionRole = ExecutionRole.TARGET) -> ExecutionRequest:
    return ExecutionRequest(
        id="execution-test",
        role=role,
        repository_directory=repository,
        command=("python", "-B", "probe.py"),
        runtime=_runtime(),
        environment={"EXPERIMENT_MODE": "test"},
    )


def test_docker_argv_enforces_isolation_without_shell(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "probe.py").write_text("print('ok')\n", encoding="utf-8")
    runner = FakeRunner()
    artifacts = FilesystemArtifactStore(tmp_path / "external")
    result = DockerExecutor(artifacts, runner).execute(_request(repository))
    assert result.status is ExecutionStatus.COMPLETED
    assert runner.preflight_called
    arguments = runner.arguments or []
    assert arguments[0:2] == ["docker", "run"]
    assert "--read-only" in arguments
    assert ["--cap-drop", "ALL"] == arguments[
        arguments.index("--cap-drop") : arguments.index("--cap-drop") + 2
    ]
    assert ["--network", "none"] == arguments[
        arguments.index("--network") : arguments.index("--network") + 2
    ]
    assert "no-new-privileges:true" in arguments
    assert request_command(arguments) == ["python", "-B", "probe.py"]
    assert all("EXPERIMENT_MODE=test" not in argument for argument in arguments)


def test_trusted_evaluator_gets_read_only_target_mount(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    runner = FakeRunner()
    DockerExecutor(FilesystemArtifactStore(tmp_path / "external"), runner).execute(
        _request(repository, role=ExecutionRole.TRUSTED_EVALUATOR)
    )
    mounts = [
        (runner.arguments or [])[index + 1]
        for index, value in enumerate(runner.arguments or [])
        if value == "--mount"
    ]
    assert any("dst=/workspace/target,readonly" in mount for mount in mounts)


def test_timeout_is_structured_and_preserves_evidence(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    runner = FakeRunner(ProcessOutcome(None, b"partial", b"timeout", True))
    result = DockerExecutor(FilesystemArtifactStore(tmp_path / "external"), runner).execute(
        _request(repository)
    )
    assert result.status is ExecutionStatus.TIMED_OUT
    assert result.error_kind == "execution_timeout"
    assert result.exit_code is None


def test_executor_rejects_environment_file_injection(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    request = _request(repository)
    request = ExecutionRequest(
        request.id,
        request.role,
        request.repository_directory,
        request.command,
        request.runtime,
        {"SAFE_NAME": "first\nINJECTED=value"},
    )
    with pytest.raises(ConfigurationError, match="single-line"):
        DockerExecutor(FilesystemArtifactStore(tmp_path / "external"), FakeRunner()).execute(
            request
        )


def test_executor_rejects_unpinned_image_before_runner(tmp_path: Path) -> None:
    payload = yaml.safe_load(RUNTIME_FILE.read_text(encoding="utf-8"))
    payload["image"] = "python:3.12-slim"
    with pytest.raises(ConfigurationError, match="pinned"):
        RuntimeProfile.from_mapping(payload)


def request_command(arguments: list[str]) -> list[str]:
    image_index = next(index for index, value in enumerate(arguments) if "@sha256:" in value)
    return arguments[image_index + 1 :]


@pytest.mark.docker
@pytest.mark.skipif(
    os.environ.get("MS_AGENT_EVAL_RUN_DOCKER_TESTS") != "1",
    reason="set MS_AGENT_EVAL_RUN_DOCKER_TESTS=1 to run the Docker integration",
)
def test_python_312_uv_runtime_is_network_isolated(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / "probe.py").write_text(
        """
import json
import pathlib
import socket
import subprocess
import sys

network = "open"
try:
    socket.create_connection(("1.1.1.1", 53), timeout=0.5)
except OSError:
    network = "blocked"

payload = {
    "python": list(sys.version_info[:3]),
    "uv": subprocess.check_output(["uv", "--version"], text=True).strip(),
    "network": network,
}
assert payload["python"] >= [3, 12, 0]
assert payload["network"] == "blocked"
pathlib.Path("/workspace/output/probe.json").write_text(json.dumps(payload))
print(json.dumps(payload))
""".lstrip(),
        encoding="utf-8",
    )
    artifacts = FilesystemArtifactStore(tmp_path / "external")
    result = DockerExecutor(artifacts).execute(_request(repository))
    assert result.status is ExecutionStatus.COMPLETED
    assert result.output_artifact is not None
    with artifacts.get_blob(result.output_artifact) as archive_file:
        archive_path = tmp_path / "output.tar"
        archive_path.write_bytes(archive_file.read())
    with tarfile.open(archive_path) as archive:
        payload = json.load(archive.extractfile("probe.json"))  # type: ignore[arg-type]
    assert payload["python"][:2] == [3, 12]
    assert payload["uv"].startswith("uv ")
    assert payload["network"] == "blocked"
