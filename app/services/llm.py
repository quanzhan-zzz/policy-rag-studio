import json
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings


class LLMProviderError(RuntimeError):
    """Raised when the configured text model cannot produce a response."""


class LLMRateLimitError(LLMProviderError):
    def __init__(self, message: str, retry_after_seconds: float = 2.0) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    usage: TokenUsage


@dataclass(frozen=True, slots=True)
class StreamChunk:
    content: str
    usage: TokenUsage | None = None


class LLMProvider(Protocol):
    name: str

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str: ...

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> Iterator[str]: ...

    def chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> ChatResult: ...

    def stream_chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> Iterator[StreamChunk]: ...


def _usage(payload: dict) -> TokenUsage | None:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    return TokenUsage(
        prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage.get("completion_tokens", 0) or 0),
        total_tokens=int(usage.get("total_tokens", 0) or 0),
    )


def iter_sse_content(lines: Iterable[str]) -> Iterator[str]:
    for line in lines:
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
            content = payload["choices"][0]["delta"].get("content", "")
        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
            continue
        if isinstance(content, str) and content:
            yield content


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

    def chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> ChatResult:
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
            if error.response.status_code == 429:
                retry_after = error.response.headers.get("retry-after", "2")
                try:
                    retry_after_seconds = float(retry_after)
                except ValueError:
                    retry_after_seconds = 2.0
                raise LLMRateLimitError(
                    "文本模型服务触发限流",
                    retry_after_seconds=retry_after_seconds,
                ) from error
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
                return ChatResult(content=content, usage=_usage(payload) or TokenUsage())
        raise LLMProviderError("文本模型返回了空回答")

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        return self.chat_with_usage(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ).content

    def stream_chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> Iterator[StreamChunk]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                with client.stream(
                    "POST",
                    f"{self.api_base}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": list(messages),
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "stream": True,
                        "stream_options": {"include_usage": True},
                    },
                ) as response:
                    if response.is_error:
                        raise LLMProviderError(
                            f"文本模型服务返回 HTTP {response.status_code}"
                        )
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line.removeprefix("data:").strip()
                        if not data or data == "[DONE]":
                            continue
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        usage = _usage(payload)
                        try:
                            content = payload["choices"][0]["delta"].get("content", "")
                        except (KeyError, IndexError, TypeError):
                            content = ""
                        if usage is not None:
                            yield StreamChunk(content="", usage=usage)
                        if isinstance(content, str) and content:
                            yield StreamChunk(content=content)
        except LLMProviderError:
            raise
        except httpx.TimeoutException as error:
            raise LLMProviderError("文本模型流式请求超时") from error
        except httpx.RequestError as error:
            raise LLMProviderError("无法连接文本模型流式服务") from error

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> Iterator[str]:
        for chunk in self.stream_chat_with_usage(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.content:
                yield chunk.content


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    return OpenAICompatibleChatProvider(
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key or "",
        model=settings.llm_model,
    )
