from __future__ import annotations

import json
from pathlib import Path

import dspy
import pytest
from ms_agent_eval.core.models import ProgramSpecification
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.providers import ModelCallObserver
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.programs.dspy import (
    DspyProgramEngine,
    create_program,
    load_state_json,
    save_state_json,
)


class RecordingDummyLM(dspy.utils.DummyLM):
    def __init__(self, answers, observer):  # type: ignore[no-untyped-def]
        super().__init__(answers)
        self.model = "dummy/deterministic"
        self.observer = observer

    def forward(self, prompt=None, messages=None, **kwargs):  # type: ignore[no-untyped-def]
        rendered = messages or [{"role": "user", "content": prompt}]
        response = super().forward(prompt=prompt, messages=messages, **kwargs)
        response["model"] = self.model
        self.observer.completed(
            provider_id="dummy",
            model=self.model,
            parameters={"temperature": 0},
            messages=rendered,
            request={"model": self.model, "messages": rendered},
            response=response,
            usage={},
            latency_seconds=0.0,
            configured_cost=0.0,
        )
        return response


def _specification() -> ProgramSpecification:
    return ProgramSpecification.from_mapping(
        {
            "schema_version": 1,
            "id": "instruction-response-v1",
            "engine": "dspy",
            "payload": {
                "signature": {
                    "inputs": ["global_context", "instruction_context", "task"],
                    "outputs": {"response": "str"},
                },
                "module": "predict",
                "adapter": "chat",
            },
        }
    )


def test_dspy_engine_returns_typed_output_and_rendered_call(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "external")
    observer = ModelCallObserver(store)
    lm = RecordingDummyLM([{"response": "typed answer"}], observer)
    result = DspyProgramEngine(store).execute(
        specification=_specification(),
        inputs=ProgramInputs("global", "unit", "task"),
        lm=lm,
        observer=observer,
    )
    assert result.status == "completed"
    assert result.outputs == {"response": "typed answer"}
    assert result.primary_response == "typed answer"
    assert len(result.calls) == 1
    rendered = json.dumps(result.calls[0].rendered_messages)
    assert "global" in rendered and "unit" in rendered and "task" in rendered


def test_dspy_engine_returns_structured_parse_failure(tmp_path: Path) -> None:
    store = FilesystemArtifactStore(tmp_path / "external")
    observer = ModelCallObserver(store)
    lm = RecordingDummyLM([{"not_response": "wrong"}] * 4, observer)
    result = DspyProgramEngine(store).execute(
        specification=_specification(),
        inputs=ProgramInputs("global", "unit", "task"),
        lm=lm,
        observer=observer,
    )
    assert result.status == "failed"
    assert result.primary_response is None
    assert result.error_kind is not None
    assert result.trace_artifact is not None


def test_state_round_trip_is_json_only(tmp_path: Path) -> None:
    program = create_program()
    path = tmp_path / "state.json"
    state = save_state_json(program, path)
    assert isinstance(state, dict)
    load_state_json(create_program(), path)
    with pytest.raises(Exception, match="prohibited|permitted"):
        save_state_json(program, tmp_path / "program.pkl")
