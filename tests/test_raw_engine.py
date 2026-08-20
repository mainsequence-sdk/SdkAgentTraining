from __future__ import annotations

from pathlib import Path

from ms_agent_eval.core.models import ProgramSpecification
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.providers import ModelCallObserver, ProviderResponse
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.programs.raw import RawMessageEngine, render_messages


class FakeProvider:
    id = "fake"
    model = "fake-v1"
    parameters = {"temperature": 0}
    configured_cost_per_call = 0.0

    def generate(self, messages):  # type: ignore[no-untyped-def]
        return ProviderResponse(
            "answer",
            {"model": self.model, "message": {"content": "answer"}},
            {"total_tokens": 3},
        )


def _specification() -> ProgramSpecification:
    return ProgramSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "raw-test",
            "engine": "raw",
            "payload": {
                "system_template": "Global:\n{global_context}\n\nUnit:\n{instruction_context}\n",
                "user_template": "{task}",
            },
        }
    )


def test_raw_engine_records_exact_rendered_request(tmp_path: Path) -> None:
    inputs = ProgramInputs("global", "unit", "do work")
    messages = render_messages(_specification(), inputs)
    observer = ModelCallObserver(FilesystemArtifactStore(tmp_path / "external"))
    result = RawMessageEngine().execute(
        specification=_specification(),
        inputs=inputs,
        provider=FakeProvider(),
        observer=observer,
    )
    assert result.status == "completed"
    assert result.primary_response == "answer"
    assert result.calls[0].rendered_messages == messages
    assert result.calls[0].usage == {"total_tokens": 3}
    assert result.trace_artifact is not None
