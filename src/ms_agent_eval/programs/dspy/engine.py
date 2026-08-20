from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

import dspy
from ms_agent_eval.core.errors import ConfigurationError, IntegrityError
from ms_agent_eval.core.hashing import canonical_json_bytes
from ms_agent_eval.core.models import ArtifactReference, ProgramResult, ProgramSpecification
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.providers import ModelCallObserver
from ms_agent_eval.core.storage import ArtifactStore


class InstructionResponse(dspy.Signature):
    """Answer the task using the supplied repository instruction context."""

    global_context: str = dspy.InputField(
        desc="Global instructions extracted from the locked target snapshot."
    )
    instruction_context: str = dspy.InputField(
        desc="Selected instruction-unit content from the locked target snapshot."
    )
    task: str = dspy.InputField(desc="The evaluation case presented to the model.")
    response: str = dspy.OutputField(desc="The final answer to evaluate.")


def create_program() -> dspy.Predict:
    return dspy.Predict(InstructionResponse)


def program_state(program: dspy.Module) -> dict[str, object]:
    predictors = []
    for name, predictor in program.named_predictors():
        demonstrations = []
        for example in predictor.demos:
            if hasattr(example, "toDict"):
                demonstrations.append(dict(example.toDict()))
            elif isinstance(example, Mapping):
                demonstrations.append(dict(example))
            else:
                raise IntegrityError(
                    f"unsupported DSPy demonstration state: {type(example).__name__}"
                )
        predictors.append(
            {
                "name": name,
                "instructions": predictor.signature.instructions,
                "input_fields": list(predictor.signature.input_fields),
                "output_fields": list(predictor.signature.output_fields),
                "demos": demonstrations,
            }
        )
    return {"predictors": predictors}


def save_state_json(program: dspy.Module, path: Path) -> Mapping[str, object]:
    if path.suffix != ".json":
        raise ConfigurationError("only DSPy state-only JSON artifacts are permitted")
    path.parent.mkdir(parents=True, exist_ok=True)
    program.save(str(path), save_program=False)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise IntegrityError("DSPy state JSON must contain an object")
    return payload


def load_state_json(program: dspy.Module, path: Path) -> None:
    if path.suffix != ".json":
        raise ConfigurationError("pickle and full-program DSPy artifacts are prohibited")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise IntegrityError("DSPy state JSON must contain an object")
    program.load(str(path), allow_pickle=False, allow_unsafe_lm_state=False)


def _failure_kind(error: Exception) -> str:
    name = type(error).__name__
    message = str(error).lower()
    if "parse" in name.lower() or "parse" in message or "output fields" in message:
        return "typed_output_parse_error"
    return name


class DspyProgramEngine:
    id = "dspy"

    def __init__(self, store: ArtifactStore) -> None:
        self.store = store

    def execute(
        self,
        *,
        specification: ProgramSpecification,
        inputs: ProgramInputs,
        lm: dspy.BaseLM,
        observer: ModelCallObserver,
        program: dspy.Module | None = None,
        adapter: dspy.Adapter | None = None,
    ) -> ProgramResult:
        if specification.engine != self.id:
            raise ConfigurationError("DspyProgramEngine requires engine: dspy")
        student = program or create_program()
        selected_adapter = adapter or dspy.ChatAdapter(use_json_adapter_fallback=False)
        start = len(observer.records)
        values = {
            "global_context": inputs.global_context,
            "instruction_context": inputs.instruction_context,
            "task": inputs.task,
        }
        try:
            with dspy.context(lm=lm, adapter=selected_adapter):
                prediction = student(**values)
            outputs = dict(prediction.toDict())
            response = outputs.get("response")
            if not isinstance(response, str):
                raise IntegrityError("DSPy response field was not a string")
            trace = self._trace(
                {
                    "engine": self.id,
                    "engine_version": str(dspy.__version__),
                    "program_hash": specification.content_hash,
                    "program_state": program_state(student),
                    "inputs": values,
                    "outputs": outputs,
                }
            )
            return ProgramResult(
                outputs=outputs,
                primary_response=response,
                calls=tuple(observer.records[start:]),
                trace_artifact=trace,
                status="completed",
                error_kind=None,
            )
        except Exception as error:
            kind = _failure_kind(error)
            trace = self._trace(
                {
                    "engine": self.id,
                    "engine_version": str(dspy.__version__),
                    "program_hash": specification.content_hash,
                    "program_state": program_state(student),
                    "inputs": values,
                    "error_kind": kind,
                    "error": str(error),
                }
            )
            return ProgramResult(
                outputs={},
                primary_response=None,
                calls=tuple(observer.records[start:]),
                trace_artifact=trace,
                status="failed",
                error_kind=kind,
            )

    def save_state_artifact(self, program: dspy.Module) -> ArtifactReference:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            save_state_json(program, path)
            with path.open("rb") as content:
                return self.store.put_blob(content, "application/json")

    def _trace(self, value: object) -> ArtifactReference:
        return self.store.put_blob(
            BytesIO(canonical_json_bytes(value)), "application/json"
        )
