from __future__ import annotations

import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from typing import Protocol
from uuid import uuid4

from .hashing import canonical_json_bytes, json_value
from .models import ArtifactReference, ModelCallRecord
from .storage import ArtifactStore


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    payload: Mapping[str, object]
    usage: Mapping[str, object]


class ModelProvider(Protocol):
    id: str
    model: str
    parameters: Mapping[str, object]
    configured_cost_per_call: float

    def generate(
        self, messages: Sequence[Mapping[str, object]]
    ) -> ProviderResponse: ...


class ModelCallObserver:
    def __init__(self, store: ArtifactStore) -> None:
        self.store = store
        self.records: list[ModelCallRecord] = []

    def call(
        self,
        provider: ModelProvider,
        messages: Sequence[Mapping[str, object]],
    ) -> ProviderResponse:
        started = time.monotonic()
        normalized_messages = tuple(json_value(message) for message in messages)
        request = {
            "provider": provider.id,
            "model": provider.model,
            "parameters": provider.parameters,
            "messages": normalized_messages,
        }
        try:
            response = provider.generate(messages)
            self.completed(
                provider_id=provider.id,
                model=provider.model,
                parameters=provider.parameters,
                messages=normalized_messages,  # type: ignore[arg-type]
                request=request,
                response=response.payload,
                usage=response.usage,
                latency_seconds=time.monotonic() - started,
                configured_cost=provider.configured_cost_per_call,
            )
            return response
        except Exception as error:
            self.failed(
                provider_id=provider.id,
                model=provider.model,
                parameters=provider.parameters,
                messages=normalized_messages,  # type: ignore[arg-type]
                request=request,
                error=error,
                latency_seconds=time.monotonic() - started,
                configured_cost=provider.configured_cost_per_call,
            )
            raise

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
        return self.store.put_blob(
            BytesIO(canonical_json_bytes(value)), "application/json"
        )
