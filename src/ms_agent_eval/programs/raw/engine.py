from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO

from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.hashing import canonical_json_bytes
from ms_agent_eval.core.models import ProgramResult, ProgramSpecification
from ms_agent_eval.core.programs import ProgramInputs
from ms_agent_eval.core.providers import ModelCallObserver, ModelProvider


def _template(payload: Mapping[str, object], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ConfigurationError(f"raw program payload requires non-empty {name!r}")
    return value


def render_messages(
    specification: ProgramSpecification, inputs: ProgramInputs
) -> tuple[Mapping[str, object], ...]:
    if specification.engine != "raw":
        raise ConfigurationError("RawMessageEngine requires engine: raw")
    values = {
        "global_context": inputs.global_context,
        "instruction_context": inputs.instruction_context,
        "task": inputs.task,
    }
    try:
        system = _template(specification.payload, "system_template").format_map(values)
        user = _template(specification.payload, "user_template").format_map(values)
    except (KeyError, ValueError) as error:
        raise ConfigurationError(f"raw message template could not be rendered: {error}") from error
    return (
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    )


class RawMessageEngine:
    id = "raw"

    def execute(
        self,
        *,
        specification: ProgramSpecification,
        inputs: ProgramInputs,
        provider: ModelProvider,
        observer: ModelCallObserver,
    ) -> ProgramResult:
        start = len(observer.records)
        try:
            messages = render_messages(specification, inputs)
            response = observer.call(provider, messages)
            trace = observer.store.put_blob(
                BytesIO(
                    canonical_json_bytes(
                        {
                            "engine": self.id,
                            "program_hash": specification.content_hash,
                            "messages": messages,
                            "output": response.text,
                        }
                    )
                ),
                "application/json",
            )
            return ProgramResult(
                outputs={"response": response.text},
                primary_response=response.text,
                calls=tuple(observer.records[start:]),
                trace_artifact=trace,
                status="completed",
                error_kind=None,
            )
        except Exception as error:
            trace = observer.store.put_blob(
                BytesIO(
                    canonical_json_bytes(
                        {
                            "engine": self.id,
                            "program_hash": specification.content_hash,
                            "error_kind": type(error).__name__,
                            "error": str(error),
                        }
                    )
                ),
                "application/json",
            )
            return ProgramResult(
                outputs={},
                primary_response=None,
                calls=tuple(observer.records[start:]),
                trace_artifact=trace,
                status="failed",
                error_kind=type(error).__name__,
            )
