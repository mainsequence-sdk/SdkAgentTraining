from __future__ import annotations

from pathlib import Path

from ms_agent_eval.core.providers import ModelCallObserver
from ms_agent_eval.core.storage import FilesystemArtifactStore
from ms_agent_eval.providers.ollama import OllamaProvider, build_chat_request


def test_raw_request_shape_and_observation_are_exact(tmp_path: Path) -> None:
    captured = []

    def transport(url, payload, timeout):  # type: ignore[no-untyped-def]
        captured.append((url, payload, timeout))
        return {
            "model": "example",
            "message": {"role": "assistant", "content": "answer"},
            "prompt_eval_count": 7,
            "eval_count": 2,
            "done": True,
        }

    provider = OllamaProvider(
        model="example",
        base_url="http://127.0.0.1:11434",
        parameters={"temperature": 0.0},
        transport=transport,
    )
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "task"},
    ]
    observer = ModelCallObserver(FilesystemArtifactStore(tmp_path / "external"))
    response = observer.call(provider, messages)
    assert response.text == "answer"
    assert response.usage["total_tokens"] == 9
    assert captured[0][1] == build_chat_request(
        model="example", messages=messages, parameters={"temperature": 0.0}
    )
    assert observer.records[0].rendered_messages == tuple(messages)


def test_dspy_binding_disables_litellm_retries_and_cache(tmp_path: Path) -> None:
    provider = OllamaProvider(
        model="example",
        base_url="http://127.0.0.1:11434",
        parameters={"temperature": 0.0},
    )
    observer = ModelCallObserver(FilesystemArtifactStore(tmp_path / "external"))
    lm = provider.create_dspy_lm(observer)
    assert lm.model == "ollama_chat/example"
    assert lm.cache is False
    assert lm.num_retries == 0
