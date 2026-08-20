from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from .models import ProgramResult, ProgramSpecification
from .providers import ModelCallObserver, ModelProvider


@dataclass(frozen=True)
class ProgramInputs:
    global_context: str
    instruction_context: str
    task: str


class ProgramEngine(Protocol):
    id: str

    def execute(
        self,
        *,
        specification: ProgramSpecification,
        inputs: ProgramInputs,
        provider: ModelProvider,
        observer: ModelCallObserver,
    ) -> ProgramResult: ...


@dataclass(frozen=True)
class EngineProviderBinding:
    engine: str
    provider_id: str
    configuration: Mapping[str, object]
