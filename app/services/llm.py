from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings


class LLMProviderError(RuntimeError):
    """Raised when the configured text model cannot produce a response."""


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str: ...


class OpenAICompatibleChatProvider:
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 90.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.name = f"OpenAI-compatible chat · {model}"

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": list(messages),
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as error:
            raise LLMProviderError("文本模型请求超时，请稍后重试") from error
        except httpx.HTTPStatusError as error:
            raise LLMProviderError(
                f"文本模型服务返回 HTTP {error.response.status_code}"
            ) from error
        except httpx.RequestError as error:
            raise LLMProviderError("无法连接文本模型服务") from error
        except ValueError as error:
            raise LLMProviderError("文本模型返回了无效的 JSON") from error

        try:
            content = payload["choices"][0]["message"].get("content", "")
        except (KeyError, IndexError, TypeError) as error:
            raise LLMProviderError("文本模型响应缺少 choices/message 字段") from error
        if isinstance(content, str):
            content = content.strip()
            if content:
                return content
        raise LLMProviderError("文本模型返回了空回答")


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return OpenAICompatibleChatProvider(
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model,
    )
