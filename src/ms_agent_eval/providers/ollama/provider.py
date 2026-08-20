from __future__ import annotations

from urllib.parse import urlparse

from ms_agent_eval.core.errors import ConfigurationError
from ms_agent_eval.core.providers import ModelCallObserver
from ms_agent_eval.core.workspace import ResolvedRoleModel
from ms_agent_eval.programs.dspy.budget import BudgetLedger
from ms_agent_eval.programs.dspy.observed_lm import ObservedDspyLM


def create_observed_lm(
    model: ResolvedRoleModel,
    observer: ModelCallObserver,
    *,
    budget: BudgetLedger | None = None,
) -> ObservedDspyLM:
    """Bind a resolved Ollama role directly to the canonical observed DSPy LM."""

    if model.provider != "ollama":
        raise ConfigurationError(f"unsupported DSPy provider: {model.provider}")
    endpoint = urlparse(model.endpoint)
    if endpoint.scheme not in {"http", "https"} or not endpoint.hostname:
        raise ConfigurationError("Ollama endpoint must be an HTTP(S) URL")
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ConfigurationError("Ollama endpoint must not embed credentials/query/fragment")
    return ObservedDspyLM(
        provider_id=model.provider,
        model=f"ollama_chat/{model.model}",
        observer=observer,
        configured_cost_per_call=model.configured_cost_per_call,
        budget=budget,
        api_base=model.endpoint.rstrip("/"),
        api_key="",
        cache=False,
        **dict(model.parameters),
    )
