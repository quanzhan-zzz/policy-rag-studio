import asyncio
import re
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from threading import Event
from typing import Any

from app.config import get_settings
from app.schemas import (
    AnswerCitation,
    AnswerRequest,
    AnswerResponse,
    CitationVerifierProvider,
    ClaimVerificationRecord,
    QueryPlanningMode,
    RetrievalRun,
    RetrievalStrategy,
    RetrievedChunk,
    TraceStage,
)
from app.services.citation_verification import VerificationResult, verify_answer
from app.services.llm import LLMProvider, TokenUsage, get_llm_provider
from app.services.query_planning import plan_query
from app.services.retrieval import (
    prepare_dense_scores,
    run_planned_retrieval,
    run_retrieval,
)
from app.store import Store

SYSTEM_PROMPT = """你是政务政策检索助手。
你只能依据给出的政策片段回答，不得补充片段之外的事实。
如果片段不足，请明确说明“根据当前检索到的政策片段无法确认”。
回答中的每个关键结论后使用 [1]、[2] 这样的编号标注来源。
回答要简洁、准确，并保留必要的办理条件、材料和地点信息。"""

CITATION_PATTERN = re.compile(r"\[(\d+)\]")
REMOVED_CLAIM_TEXT = "[已移除的不受支持结论]"


@dataclass(frozen=True, slots=True)
class AnswerPreparation:
    provider: LLMProvider
    run: RetrievalRun
    citations: list[AnswerCitation]
    messages: list[dict[str, str]]
    started_at: float


@dataclass(frozen=True, slots=True)
class StreamEvent:
    event: str
    data: dict[str, Any]


def build_context(results: Sequence[RetrievedChunk]) -> tuple[str, list[AnswerCitation]]:
    context_parts: list[str] = []
    citations: list[AnswerCitation] = []
    for index, result in enumerate(results, start=1):
        context_parts.append(
            f"[{index}] {result.document_title} · {result.heading_path} · 第{result.page}页\n"
            f"{result.text}"
        )
        citations.append(
            AnswerCitation(
                source_id=index,
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_title=result.document_title,
                heading_path=result.heading_path,
                page=result.page,
                text=result.text,
            )
        )
    return "\n\n".join(context_parts), citations


def apply_grounding_guard(
    answer: str,
    citations: Sequence[AnswerCitation],
) -> tuple[str, list[int], list[int], str]:
    valid_ids, invalid_ids = validate_citations(answer, citations)
    if not valid_ids:
        status = "uncited"
        notice = "\n\n[证据提示] 当前回答未包含可验证引用，请以原文片段为准。"
    elif invalid_ids:
        status = "invalid_citations"
        refs = "、".join(f"[{source_id}]" for source_id in invalid_ids)
        notice = f"\n\n[证据提示] 检测到无效引用 {refs}，请以引用原文为准。"
    else:
        status = "supported"
        notice = ""
    if notice and notice.strip() not in answer:
        answer = f"{answer.rstrip()}{notice}"
    return answer, valid_ids, invalid_ids, status


async def _verify_answer(
    answer: str,
    citations: list[AnswerCitation],
    *,
    request: AnswerRequest,
    llm_provider: LLMProvider,
) -> VerificationResult:
    settings = get_settings()
    provider = request.citation_verifier_provider or CitationVerifierProvider(
        settings.citation_verifier_provider
    )
    return await verify_answer(
        request.query,
        answer,
        citations,
        provider=provider,
        timeout_seconds=settings.citation_verifier_timeout_seconds,
        llm_provider=llm_provider,
    )


def _verification_grounding_status(
    verification: VerificationResult,
    citation_guard_status: str,
) -> str:
    if verification.status in {"abstained", "verification_failed"}:
        return verification.status
    if verification.status == "partially_supported":
        return "partially_supported"
    return citation_guard_status


def _verification_claims(
    verification: VerificationResult,
) -> list[ClaimVerificationRecord]:
    return [
        ClaimVerificationRecord(
            text=claim.text if claim.supported else REMOVED_CLAIM_TEXT,
            verified_text=claim.verified_text if claim.supported else REMOVED_CLAIM_TEXT,
            supported=claim.supported,
            citation_ids=list(claim.citation_ids),
            supported_citation_ids=list(claim.supported_citation_ids),
            reason=claim.reason,
            failure_type=claim.failure_type,
        )
        for claim in verification.claims
    ]


def _verification_trace_detail(verification: VerificationResult) -> str:
    fallback = f" · fallback={verification.fallback_reason}" if verification.fallback_reason else ""
    return (
        f"{verification.verifier}:{verification.status} · "
        f"supported={verification.supported_claim_count} "
        f"removed={verification.removed_claim_count} "
        f"removed_citations={verification.removed_citation_count} · "
        f"tokens={verification.usage.total_tokens}{fallback}"
    )


def validate_citations(
    answer: str,
    citations: Sequence[AnswerCitation],
) -> tuple[list[int], list[int]]:
    valid_ids = {citation.source_id for citation in citations}
    referenced = {int(match) for match in CITATION_PATTERN.findall(answer)}
    return sorted(referenced & valid_ids), sorted(referenced - valid_ids)


async def prepare_answer(
    store: Store,
    request: AnswerRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AnswerPreparation:
    started_at = time.perf_counter()
    filter_started = time.perf_counter()
    chunks = await store.all_chunks(
        request.chunk_strategy,
        filters=request.filters,
    )
    if not chunks:
        if request.filters is not None and request.filters.has_conditions():
            raise ValueError("没有符合筛选条件的可检索内容")
        raise ValueError("当前切片策略下没有可检索内容")
    unfiltered_chunk_count = (
        await store.count_chunks_for_strategy(request.chunk_strategy)
        if request.filters is not None and request.filters.has_conditions()
        else None
    )
    filter_latency_ms = (time.perf_counter() - filter_started) * 1000
    provider = llm_provider or get_llm_provider()
    settings = get_settings()
    mode = request.query_planning_mode or QueryPlanningMode(settings.query_planning_mode)
    if mode is QueryPlanningMode.NONE:
        embedding_provider, dense_scores, dense_latency_ms = await prepare_dense_scores(
            store,
            chunks,
            request.query,
            request.chunk_strategy,
            filters=request.filters,
        )
        run, trace = await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=request.query,
            strategy=RetrievalStrategy.HYBRID_RERANK,
            chunk_strategy=request.chunk_strategy,
            top_k=request.top_k,
            embedding_provider=embedding_provider,
            dense_scores_by_chunk=dense_scores,
            precomputed_latency_ms=dense_latency_ms,
            filters=request.filters,
            unfiltered_chunk_count=unfiltered_chunk_count,
            filter_latency_ms=filter_latency_ms,
        )
    else:
        plan = await plan_query(
            request.query,
            mode,
            llm_provider=provider,
            timeout_seconds=settings.query_planning_timeout_seconds,
            max_subqueries=settings.query_planning_max_subqueries,
        )
        run, trace = await run_planned_retrieval(
            store,
            chunks,
            plan,
            top_k=request.top_k,
            filters=request.filters,
            unfiltered_chunk_count=unfiltered_chunk_count,
            filter_latency_ms=filter_latency_ms,
        )
    await store.record_trace(trace)
    context, citations = build_context(run.results)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"用户问题：{request.query}\n\n检索到的政策片段：\n{context}",
        },
    ]
    return AnswerPreparation(
        provider=provider,
        run=run,
        citations=citations,
        messages=messages,
        started_at=started_at,
    )


async def answer_query(
    store: Store,
    request: AnswerRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AnswerResponse:
    prepared = await prepare_answer(store, request, llm_provider=llm_provider)
    chat_with_usage = getattr(prepared.provider, "chat_with_usage", None)
    usage = TokenUsage()
    if callable(chat_with_usage):
        result = await asyncio.to_thread(
            chat_with_usage,
            prepared.messages,
            temperature=request.temperature,
            max_tokens=900,
        )
        answer = result.content
        usage = result.usage
    else:
        answer = await asyncio.to_thread(
            prepared.provider.chat,
            prepared.messages,
            temperature=request.temperature,
            max_tokens=900,
        )
    verification = await _verify_answer(
        answer,
        prepared.citations,
        request=request,
        llm_provider=prepared.provider,
    )
    answer = verification.answer
    answer, _, invalid_ids, grounding_status = apply_grounding_guard(
        answer,
        prepared.citations,
    )
    grounding_status = _verification_grounding_status(verification, grounding_status)
    total_ms = (time.perf_counter() - prepared.started_at) * 1000
    await store.complete_trace_generation(
        prepared.run.trace_id,
        TraceStage(
            key="generation",
            label="回答生成",
            duration_ms=round(max(0.0, total_ms - prepared.run.latency_ms), 3),
            input_count=len(prepared.citations),
            output_count=usage.completion_tokens or len(answer),
            detail=(
                f"{prepared.provider.name} · {grounding_status} · "
                f"tokens {usage.prompt_tokens}/{usage.completion_tokens} · "
                f"verify {verification.verifier}:{verification.status} "
                f"removed={verification.removed_claim_count}"
            ),
        ),
        total_ms,
    )
    await store.complete_trace_generation(
        prepared.run.trace_id,
        TraceStage(
            key="verification",
            label="引用支持核验",
            duration_ms=verification.latency_ms,
            input_count=len(verification.claims),
            output_count=verification.supported_claim_count,
            detail=_verification_trace_detail(verification),
        ),
        total_ms,
    )
    return AnswerResponse(
        query=request.query,
        answer=answer,
        model=prepared.provider.name,
        retrieval=prepared.run,
        citations=prepared.citations,
        total_ms=round(total_ms, 3),
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        invalid_citation_ids=invalid_ids,
        grounding_status=grounding_status,
        verification_provider=verification.verifier,
        verification_status=verification.status,
        verified_claim_count=verification.supported_claim_count,
        removed_claim_count=verification.removed_claim_count,
        removed_citation_count=verification.removed_citation_count,
        verification_tokens=verification.usage.total_tokens,
        verification_ms=verification.latency_ms,
        verification_fallback_reason=verification.fallback_reason,
        verification_claims=_verification_claims(verification),
    )


async def stream_answer_query(
    store: Store,
    request: AnswerRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AsyncIterator[StreamEvent]:
    prepared = await prepare_answer(store, request, llm_provider=llm_provider)
    yield StreamEvent(
        "meta",
        {
            "query": request.query,
            "model": prepared.provider.name,
            "retrieval": prepared.run.model_dump(mode="json"),
            "citations": [citation.model_dump(mode="json") for citation in prepared.citations],
        },
    )

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, str | TokenUsage | Exception | None]] = asyncio.Queue()
    first_token_ms: float | None = None
    generation_started = time.perf_counter()
    usage = TokenUsage()
    cancelled = Event()

    def produce() -> None:
        try:
            stream = getattr(prepared.provider, "stream_chat_with_usage", None)
            if callable(stream):
                for chunk in stream(
                    prepared.messages,
                    temperature=request.temperature,
                    max_tokens=900,
                ):
                    if cancelled.is_set():
                        break
                    if chunk.content:
                        loop.call_soon_threadsafe(queue.put_nowait, ("delta", chunk.content))
                    if chunk.usage:
                        loop.call_soon_threadsafe(queue.put_nowait, ("usage", chunk.usage))
            else:
                legacy_stream = getattr(prepared.provider, "stream_chat", None)
                if callable(legacy_stream):
                    for content in legacy_stream(
                        prepared.messages,
                        temperature=request.temperature,
                        max_tokens=900,
                    ):
                        if cancelled.is_set():
                            break
                        loop.call_soon_threadsafe(queue.put_nowait, ("delta", content))
                else:
                    content = prepared.provider.chat(
                        prepared.messages,
                        temperature=request.temperature,
                        max_tokens=900,
                    )
                    loop.call_soon_threadsafe(queue.put_nowait, ("delta", content))
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))
        except Exception as error:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", error))

    producer = asyncio.create_task(asyncio.to_thread(produce))
    parts: list[str] = []
    try:
        while True:
            event_type, payload = await queue.get()
            if event_type == "delta" and isinstance(payload, str):
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - generation_started) * 1000
                parts.append(payload)
                yield StreamEvent("delta", {"content": payload})
            elif event_type == "usage" and isinstance(payload, TokenUsage):
                usage = payload
            elif event_type == "error" and isinstance(payload, Exception):
                total_ms = (time.perf_counter() - prepared.started_at) * 1000
                await store.complete_trace_generation(
                    prepared.run.trace_id,
                    TraceStage(
                        key="generation",
                        label="回答生成失败",
                        duration_ms=round(max(0.0, total_ms - prepared.run.latency_ms), 3),
                        input_count=len(prepared.citations),
                        output_count=0,
                        detail=f"{type(payload).__name__}: {str(payload)[:300]}",
                    ),
                    total_ms,
                )
                yield StreamEvent(
                    "error",
                    {"message": str(payload), "error_type": type(payload).__name__},
                )
                return
            elif event_type == "done":
                break
    finally:
        cancelled.set()
        await producer

    answer = "".join(parts)
    verification = await _verify_answer(
        answer,
        prepared.citations,
        request=request,
        llm_provider=prepared.provider,
    )
    answer = verification.answer
    answer, _, invalid_ids, grounding_status = apply_grounding_guard(
        answer,
        prepared.citations,
    )
    grounding_status = _verification_grounding_status(verification, grounding_status)
    total_ms = (time.perf_counter() - prepared.started_at) * 1000
    await store.complete_trace_generation(
        prepared.run.trace_id,
        TraceStage(
            key="generation",
            label="流式回答生成",
            duration_ms=round(max(0.0, total_ms - prepared.run.latency_ms), 3),
            input_count=len(prepared.citations),
            output_count=usage.completion_tokens or len(answer),
            detail=(
                f"{prepared.provider.name} · {grounding_status} · "
                f"first token {first_token_ms or 0:.1f}ms · "
                f"tokens {usage.prompt_tokens}/{usage.completion_tokens} · "
                f"verify {verification.verifier}:{verification.status} "
                f"removed={verification.removed_claim_count}"
            ),
        ),
        total_ms,
    )
    await store.complete_trace_generation(
        prepared.run.trace_id,
        TraceStage(
            key="verification",
            label="引用支持核验",
            duration_ms=verification.latency_ms,
            input_count=len(verification.claims),
            output_count=verification.supported_claim_count,
            detail=_verification_trace_detail(verification),
        ),
        total_ms,
    )
    yield StreamEvent(
        "done",
        {
            "query": request.query,
            "answer": answer,
            "model": prepared.provider.name,
            "retrieval": prepared.run.model_dump(mode="json"),
            "citations": [citation.model_dump(mode="json") for citation in prepared.citations],
            "first_token_ms": round(first_token_ms or 0.0, 3),
            "total_ms": round(total_ms, 3),
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "invalid_citation_ids": invalid_ids,
            "grounding_status": grounding_status,
            "verification_provider": verification.verifier,
            "verification_status": verification.status,
            "verified_claim_count": verification.supported_claim_count,
            "removed_claim_count": verification.removed_claim_count,
            "removed_citation_count": verification.removed_citation_count,
            "verification_tokens": verification.usage.total_tokens,
            "verification_ms": verification.latency_ms,
            "verification_fallback_reason": verification.fallback_reason,
            "verification_claims": [
                claim.model_dump(mode="json") for claim in _verification_claims(verification)
            ],
        },
    )
