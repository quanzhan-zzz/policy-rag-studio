import httpx
import pytest

from app.services.llm import LLMProviderError, OpenAICompatibleChatProvider


def test_chat_rejects_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleChatProvider(
        api_base="http://model.test/v1",
        api_key="",
        model="test-model",
    )

    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "http://model.test/v1/chat/completions")
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": "  "}}]},
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    with pytest.raises(LLMProviderError, match="空回答"):
        provider.chat([{"role": "user", "content": "hello"}])


def test_chat_reports_upstream_status(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = OpenAICompatibleChatProvider(
        api_base="http://model.test/v1",
        api_key="test-key",
        model="test-model",
    )

    def fake_post(*args, **kwargs):
        request = httpx.Request("POST", "http://model.test/v1/chat/completions")
        return httpx.Response(503, request=request, json={"error": "unavailable"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    with pytest.raises(LLMProviderError, match="HTTP 503"):
        provider.chat([{"role": "user", "content": "hello"}])
