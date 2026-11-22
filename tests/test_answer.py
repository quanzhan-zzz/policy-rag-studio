import asyncio
import threading
import time

import pytest

from app.schemas import AnswerRequest, ChunkStrategy, RetrievalStrategy
from app.services.answer import (
    answer_query,
    apply_grounding_guard,
    build_context,
    stream_answer_query,
    validate_citations,
)
from app.services.llm import ChatResult, StreamChunk, TokenUsage
from app.services.retrieval import run_retrieval
from app.store import InMemoryStore


class FakeLLM:
    name = "fake-llm"

    def chat(self, messages, *, temperature=0.1, max_tokens=800):
        assert messages
        assert temperature == 0.1
        return "办理地点是常州市政务服务中心。[1]"


@pytest.mark.asyncio
async def test_build_context_numbers_citations() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, _ = run_retrieval(
        chunks=chunks,
        query="办理地点",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=3,
    )
    context, citations = build_context(run.results)
    assert "[1]" in context
    assert citations[0].source_id == 1
    assert citations[0].chunk_id == run.results[0].chunk_id


@pytest.mark.asyncio
async def test_answer_query_uses_injected_provider() -> None:
    store = InMemoryStore()
    response = await answer_query(
        store,
        AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=3),
        llm_provider=FakeLLM(),
    )
    assert response.query == "青年人才租房补贴在哪里办理"
    assert response.model == "fake-llm"
    assert "[1]" in response.answer
    assert response.citations


class FakeStreamingLLM:
    name = "fake-stream"

    def chat(self, messages, *, temperature=0.1, max_tokens=800):
        return "办理地点是常州市政务服务中心。[1]"

    def stream_chat(self, messages, *, temperature=0.1, max_tokens=800):
        yield "办理地点是"
        yield "常州市政务服务中心。[1]"
        yield "无效引用[9]"


@pytest.mark.asyncio
async def test_validate_citations_marks_unknown_ids() -> None:
    store = InMemoryStore()
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    run, _ = run_retrieval(
        chunks=chunks,
        query="办理地点",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=ChunkStrategy.HEADING,
        top_k=2,
    )
    _, citations = build_context(run.results)
    valid, invalid = validate_citations("结论[1] 错误[9]", citations)
    assert valid == [1]
    assert invalid == [9]


@pytest.mark.asyncio
async def test_stream_answer_emits_meta_delta_done_and_invalid_citations() -> None:
    store = InMemoryStore()
    events = [
        event
        async for event in stream_answer_query(
            store,
            AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=2),
            llm_provider=FakeStreamingLLM(),
        )
    ]
    assert [event.event for event in events] == ["meta", "delta", "delta", "delta", "done"]
    assert events[1].data["content"] == "办理地点是"
    done = events[-1].data
    assert "无效引用[9]" in done["answer"]
    assert "证据提示" in done["answer"]
    assert done["invalid_citation_ids"] == [9]
    assert done["first_token_ms"] >= 0
    assert done["total_ms"] >= 0


class FailingStreamingLLM:
    name = "failing-stream"

    def chat(self, messages, *, temperature=0.1, max_tokens=800):
        raise RuntimeError("stream unavailable")

    def stream_chat(self, messages, *, temperature=0.1, max_tokens=800):
        raise RuntimeError("stream unavailable")
        yield "unreachable"


@pytest.mark.asyncio
async def test_stream_answer_emits_error_event() -> None:
    store = InMemoryStore()
    events = [
        event
        async for event in stream_answer_query(
            store,
            AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=2),
            llm_provider=FailingStreamingLLM(),
        )
    ]
    assert events[-1].event == "error"
    assert events[-1].data["error_type"] == "RuntimeError"


class UsageStreamingLLM:
    name = "usage-stream"

    def chat(self, messages, *, temperature=0.1, max_tokens=800):
        return "回答[1]"

    def chat_with_usage(self, messages, *, temperature=0.1, max_tokens=800):
        return ChatResult("回答[1]", TokenUsage(10, 4, 14))

    def stream_chat(self, messages, *, temperature=0.1, max_tokens=800):
        yield "回答[1]"

    def stream_chat_with_usage(self, messages, *, temperature=0.1, max_tokens=800):
        yield StreamChunk("回答")
        yield StreamChunk("[1]")
        yield StreamChunk("", TokenUsage(10, 4, 14))


@pytest.mark.asyncio
async def test_answer_records_usage_and_generation_trace() -> None:
    store = InMemoryStore()
    response = await answer_query(
        store,
        AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=2),
        llm_provider=UsageStreamingLLM(),
    )
    assert response.total_tokens == 14
    trace = await store.get_trace(response.retrieval.trace_id)
    assert trace is not None
    assert trace.stages[-1].key == "generation"
    assert "tokens 10/4" in trace.stages[-1].detail


@pytest.mark.asyncio
async def test_stream_records_usage_and_generation_trace() -> None:
    store = InMemoryStore()
    events = [
        event
        async for event in stream_answer_query(
            store,
            AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=2),
            llm_provider=UsageStreamingLLM(),
        )
    ]
    done = events[-1].data
    assert done["total_tokens"] == 14
    trace = await store.get_trace(done["retrieval"]["trace_id"])
    assert trace is not None
    assert trace.stages[-1].key == "generation"


def test_grounding_guard_marks_uncited_answers() -> None:
    class Citation:
        source_id = 1

    guarded, valid, invalid, status = apply_grounding_guard("没有引用的回答", [Citation()])
    assert "证据提示" in guarded
    assert valid == []
    assert invalid == []
    assert status == "uncited"


@pytest.mark.asyncio
async def test_stream_cancellation_stops_producer() -> None:
    class CancellableStreamingLLM:
        name = "cancel-stream"

        def __init__(self) -> None:
            self.stopped = threading.Event()

        def chat(self, messages, *, temperature=0.1, max_tokens=800):
            return "unused"

        def stream_chat(self, messages, *, temperature=0.1, max_tokens=800):
            try:
                for _ in range(100):
                    yield "片段"
                    time.sleep(0.005)
            finally:
                self.stopped.set()

    provider = CancellableStreamingLLM()
    stream = stream_answer_query(
        InMemoryStore(),
        AnswerRequest(query="青年人才租房补贴在哪里办理", top_k=2),
        llm_provider=provider,
    )
    assert (await anext(stream)).event == "meta"
    assert (await anext(stream)).event == "delta"
    await stream.aclose()
    for _ in range(100):
        if provider.stopped.is_set():
            break
        await asyncio.sleep(0.01)
    assert provider.stopped.is_set()
