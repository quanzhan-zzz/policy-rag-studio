import math

from app.services.embedding import (
    CachedEmbeddingProvider,
    HashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


class CountingProvider:
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def embed_query(self, text: str) -> list[float]:
        self.calls += 1
        return [float(len(text)), 1.0]

    def embed_documents(self, texts):
        return [self.embed_query(text) for text in texts]


def test_hash_provider_is_deterministic_and_normalized() -> None:
    provider = HashEmbeddingProvider(dimensions=32)
    first = provider.embed_query("个体工商户登记")
    second = provider.embed_query("个体工商户登记")
    assert first == second
    assert math.isclose(math.sqrt(sum(value * value for value in first)), 1.0, rel_tol=1e-9)


def test_cached_provider_reuses_query_embedding() -> None:
    delegate = CountingProvider()
    provider = CachedEmbeddingProvider(delegate)
    assert provider.embed_query("政策") == provider.embed_query("政策")
    assert delegate.calls == 1


class BatchCountingProvider:
    name = "batch-counting"

    def __init__(self) -> None:
        self.batch_calls = 0

    def embed_query(self, text: str) -> list[float]:
        return [1.0, float(len(text))]

    def embed_documents(self, texts):
        self.batch_calls += 1
        return [self.embed_query(text) for text in texts]


def test_cached_documents_use_one_batch_and_reuse_cache() -> None:
    delegate = BatchCountingProvider()
    provider = CachedEmbeddingProvider(delegate)
    first = provider.embed_documents(["政策甲", "政策乙", "政策甲"])
    second = provider.embed_documents(["政策乙"])
    assert len(first) == 3
    assert second == [first[1]]
    assert delegate.batch_calls == 1


def test_openai_embedding_provider_batches_documents(monkeypatch) -> None:
    provider = OpenAICompatibleEmbeddingProvider(
        api_base="http://embedding.test/v1",
        api_key="test",
        model="test-model",
        batch_size=2,
    )
    calls: list[list[str]] = []

    def fake_embed(texts):
        calls.append(list(texts))
        return [[float(len(text)), 1.0] for text in texts]

    monkeypatch.setattr(provider, "_embed", fake_embed)
    vectors = provider.embed_documents(["甲", "乙", "丙", "丁", "戊"])

    assert [len(call) for call in calls] == [2, 2, 1]
    assert len(vectors) == 5
