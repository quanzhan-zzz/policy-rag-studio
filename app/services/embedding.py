import hashlib
import math
from collections import OrderedDict
from collections.abc import Sequence
from functools import lru_cache
from typing import Protocol

import httpx

from app.config import get_settings
from app.services.text import tokenize


class EmbeddingProvider(Protocol):
    name: str

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbeddingProvider:
    """Deterministic zero-dependency provider for tests and demo mode."""

    def __init__(self, dimensions: int = 192) -> None:
        self.dimensions = dimensions
        self.name = f"Hash embedding ({dimensions}d) · deterministic demo"

    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in tokenize(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            index = value % self.dimensions
            sign = 1.0 if (value >> 8) & 1 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        api_base: str,
        api_key: str,
        model: str,
        batch_size: int = 16,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size
        self.timeout_seconds = timeout_seconds
        self.name = f"OpenAI-compatible embedding · {model}"

    def _embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError(
                "EMBEDDING_API_KEY 未配置；请设置 EMBEDDING_API_KEY 或切换 EMBEDDING_PROVIDER=hash"
            )
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.api_base}/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "input": list(texts)},
            )
            if response.is_error:
                detail = response.text[:500].strip()
                raise RuntimeError(
                    f"Embedding API 返回 HTTP {response.status_code}: {detail}"
                )
            payload = response.json()
        ordered = sorted(payload["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in ordered]

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed(texts[start : start + self.batch_size]))
        return vectors


class BGEEmbeddingProvider:
    """Lazy local BGE provider; install with `uv sync --extra local`."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self.model_name = model_name
        self.name = f"BGE-M3 · {model_name}"
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as error:
                raise RuntimeError(
                    "本地 BGE Provider 需要 sentence-transformers；执行 "
                    "`uv sync --extra local` 后重试"
                ) from error
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        model = self._load_model()
        vector = model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return [float(value) for value in vector]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._load_model()
        vectors = model.encode(
            list(texts),
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [[float(value) for value in vector] for vector in vectors]


class CachedEmbeddingProvider:
    def __init__(self, delegate: EmbeddingProvider, maxsize: int = 4096) -> None:
        self.delegate = delegate
        self.name = delegate.name
        self.maxsize = maxsize
        self._cache: OrderedDict[str, tuple[float, ...]] = OrderedDict()

    def _remember(self, text: str, vector: Sequence[float]) -> None:
        self._cache[text] = tuple(vector)
        self._cache.move_to_end(text)
        while len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def embed_query(self, text: str) -> list[float]:
        cached = self._cache.get(text)
        if cached is not None:
            self._cache.move_to_end(text)
            return list(cached)
        vector = self.delegate.embed_query(text)
        self._remember(text, vector)
        return list(vector)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        missing = list(dict.fromkeys(text for text in texts if text not in self._cache))
        if missing:
            vectors = self.delegate.embed_documents(missing)
            for text, vector in zip(missing, vectors, strict=True):
                self._remember(text, vector)
        return [list(self._cache[text]) for text in texts]


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    provider = settings.embedding_provider
    if provider == "openai":
        delegate: EmbeddingProvider = OpenAICompatibleEmbeddingProvider(
            api_base=settings.embedding_api_base,
            api_key=settings.embedding_api_key or "",
            model=settings.openai_embedding_model,
            batch_size=settings.embedding_batch_size,
        )
    elif provider == "bge":
        delegate = BGEEmbeddingProvider(settings.bge_embedding_model)
    else:
        delegate = HashEmbeddingProvider(settings.hash_embedding_dimensions)
    return CachedEmbeddingProvider(delegate)
