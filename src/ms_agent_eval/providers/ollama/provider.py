from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ms_agent_eval.core.errors import ConfigurationError, PreflightError
from ms_agent_eval.core.providers import ModelCallObserver, ProviderResponse


Transport = Callable[[str, Mapping[str, object], float], Mapping[str, object]]


def build_chat_request(
    *,
    model: str,
    messages: Sequence[Mapping[str, object]],
    parameters: Mapping[str, object],
) -> dict[str, object]:
    return {
        "model": model,
        "stream": False,
        "messages": [dict(message) for message in messages],
        "options": dict(parameters),
    }


def _http_transport(
    url: str, payload: Mapping[str, object], timeout_seconds: float
) -> Mapping[str, object]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        result: Any = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, Mapping):
        raise RuntimeError("Ollama response must contain a JSON object")
    return {str(key): value for key, value in result.items()}


class OllamaProvider:
    id = "ollama"

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        parameters: Mapping[str, object] | None = None,
        timeout_seconds: float = 120.0,
        configured_cost_per_call: float = 0.0,
        transport: Transport = _http_transport,
    ) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ConfigurationError("Ollama base_url must be an HTTP(S) endpoint")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigurationError("Ollama base_url cannot embed credentials/query/fragment")
        if not model.strip():
            raise ConfigurationError("Ollama model must not be empty")
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.parameters = dict(parameters or {})
        self.timeout_seconds = timeout_seconds
        self.configured_cost_per_call = configured_cost_per_call
        self._transport = transport

    def generate(
        self, messages: Sequence[Mapping[str, object]]
    ) -> ProviderResponse:
        request = build_chat_request(
            model=self.model, messages=messages, parameters=self.parameters
        )
        payload = self._transport(
            f"{self.base_url}/api/chat", request, self.timeout_seconds
        )
        message = payload.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise RuntimeError("Ollama response is missing message.content")
        usage = {
            "prompt_tokens": payload.get("prompt_eval_count", 0),
            "completion_tokens": payload.get("eval_count", 0),
            "total_tokens": (
                int(payload.get("prompt_eval_count", 0) or 0)
                + int(payload.get("eval_count", 0) or 0)
            ),
        }
        return ProviderResponse(str(message["content"]), payload, usage)

    def preflight(self) -> None:
        try:
            payload = self._transport(
                f"{self.base_url}/api/chat",
                build_chat_request(
                    model=self.model,
                    messages=[{"role": "user", "content": "Reply only with OK."}],
                    parameters={**self.parameters, "num_predict": 2},
                ),
                min(self.timeout_seconds, 30.0),
            )
        except Exception as error:
            raise PreflightError("Ollama endpoint/model preflight failed") from error
        if not isinstance(payload.get("message"), Mapping):
            raise PreflightError("Ollama preflight returned an invalid response")

    def create_dspy_lm(self, observer: ModelCallObserver):  # type: ignore[no-untyped-def]
        try:
            from ms_agent_eval.programs.dspy import ObservedDspyLM
        except ImportError as error:
            raise ConfigurationError(
                "install ms-agent-eval[dspy] for the DSPy binding"
            ) from error
        return ObservedDspyLM(
            provider_id=self.id,
            model=f"ollama_chat/{self.model}",
            observer=observer,
            configured_cost_per_call=self.configured_cost_per_call,
            api_base=self.base_url,
            api_key="",
            temperature=self.parameters.get("temperature", 0.0),
            cache=False,
        )
