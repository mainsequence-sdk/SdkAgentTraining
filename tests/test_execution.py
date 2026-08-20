from __future__ import annotations

from pathlib import Path

import pytest

from ms_agent_eval.core.errors import ConfigurationError, PreflightError
from ms_agent_eval.core.execution import (
    DockerExecutor,
    ExecutionRequest,
    ExecutionStatus,
    ProcessOutcome,
)
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.core.workspace import RuntimeConfiguration


class RecordingRunner:
    def __init__(self) -> None:
        self.preflight_calls = 0
        self.arguments: list[str] = []

    def preflight(self) -> None:
        self.preflight_calls += 1

    def run(
        self,
        arguments,  # type: ignore[no-untyped-def]
        *,
        timeout_seconds: int,
        container_name: str,
        maximum_capture_bytes: int,
    ) -> ProcessOutcome:
        del timeout_seconds, container_name, maximum_capture_bytes
        self.arguments = list(arguments)
        output_mount = next(
            item
            for item in self.arguments
            if item.startswith("type=bind,") and item.endswith("dst=/workspace/output")
        )
        source = next(
            field.removeprefix("src=")
            for field in output_mount.split(",")
            if field.startswith("src=")
        )
        (Path(source) / "result.txt").write_text("container result\n", encoding="utf-8")
        return ProcessOutcome(0, b"stdout\n", b"", False)


def _runtime() -> RuntimeConfiguration:
    return RuntimeConfiguration.from_mapping(
        {
            "type": "docker",
            "python": "3.12",
            "image": "example/runtime@sha256:" + "a" * 64,
            "network": "none",
        }
    )


def test_docker_executor_uses_isolated_argv_and_external_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "input.txt").write_text("input\n", encoding="utf-8")
    store = FilesystemArtifactStore(tmp_path / "external", workspace_root=workspace)
    runner = RecordingRunner()
    executor = DockerExecutor(store, runner=runner)

    result = executor.execute(
        ExecutionRequest(
            id="case-one",
            repository_directory=target,
            command=("python", "-c", "print('ok')"),
            runtime=_runtime(),
            environment={"CASE_ID": "case-one"},
        )
    )

    assert result.status is ExecutionStatus.COMPLETED
    assert result.output_artifact is not None
    assert store.verify(result.evidence_artifact)
    assert runner.preflight_calls == 1
    for required in (
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--pids-limit",
        "--security-opt",
        "no-new-privileges:true",
        "--user",
        "65534:65534",
    ):
        assert required in runner.arguments
    assert runner.arguments[-3:] == ["python", "-c", "print('ok')"]


def test_docker_runtime_requires_digest_and_executor_rejects_response_only(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigurationError, match="digest-pinned"):
        RuntimeConfiguration.from_mapping(
            {"type": "docker", "python": "3.12", "image": "example/runtime:latest"}
        )

    response_only = RuntimeConfiguration.from_mapping({"type": "response_only", "python": "3.12"})
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executor = DockerExecutor(
        FilesystemArtifactStore(tmp_path / "external", workspace_root=workspace),
        runner=RecordingRunner(),
    )
    with pytest.raises(PreflightError, match="runtime.type=docker"):
        executor.preflight(response_only)
