from __future__ import annotations

from collections.abc import Mapping, Sequence
from io import BytesIO
from uuid import uuid4

from .hashing import canonical_json_bytes
from .models import ArtifactReference, ModelCallRecord
from .storage import ArtifactStore


class ModelCallObserver:
    """Persist observed DSPy calls for exactly one locked LLM role."""

    def __init__(
        self,
        store: ArtifactStore,
        *,
        role: str,
    ) -> None:
        if role not in {"case_builder", "solver", "judge"}:
            raise ValueError(f"invalid LLM role: {role}")
        self.store = store
        self.role = role
        self.records: list[ModelCallRecord] = []

    def completed(
        self,
        *,
        provider_id: str,
        model: str,
        parameters: Mapping[str, object],
        messages: Sequence[Mapping[str, object]],
        request: Mapping[str, object],
        response: Mapping[str, object],
        usage: Mapping[str, object],
        latency_seconds: float,
        configured_cost: float,
    ) -> ModelCallRecord:
        record = ModelCallRecord(
            call_id=str(uuid4()),
            role=self.role,  # type: ignore[arg-type]
            provider_id=provider_id,
            model=model,
            parameters=dict(parameters),
            rendered_messages=tuple(messages),
            request_artifact=self._json_artifact(request),
            response_artifact=self._json_artifact(response),
            usage=dict(usage),
            status="completed",
            error_kind=None,
            latency_seconds=latency_seconds,
            configured_cost=configured_cost,
        )
        self.records.append(record)
        return record

    def failed(
        self,
        *,
        provider_id: str,
        model: str,
        parameters: Mapping[str, object],
        messages: Sequence[Mapping[str, object]],
        request: Mapping[str, object],
        error: Exception,
        latency_seconds: float,
        configured_cost: float,
    ) -> ModelCallRecord:
        error_kind = type(error).__name__
        record = ModelCallRecord(
            call_id=str(uuid4()),
            role=self.role,  # type: ignore[arg-type]
            provider_id=provider_id,
            model=model,
            parameters=dict(parameters),
            rendered_messages=tuple(messages),
            request_artifact=self._json_artifact(request),
            response_artifact=self._json_artifact(
                {"error_kind": error_kind, "message": str(error)}
            ),
            usage={},
            status="failed",
            error_kind=error_kind,
            latency_seconds=latency_seconds,
            configured_cost=configured_cost,
        )
        self.records.append(record)
        return record

    def _json_artifact(self, value: object) -> ArtifactReference:
        return self.store.put_blob(BytesIO(canonical_json_bytes(value)), "application/json")
