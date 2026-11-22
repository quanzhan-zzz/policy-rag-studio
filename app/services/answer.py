import asyncio
from collections.abc import Sequence

from app.schemas import (
    AnswerCitation,
    AnswerRequest,
    AnswerResponse,
    RetrievalStrategy,
    RetrievedChunk,
)
from app.services.llm import LLMProvider, get_llm_provider
from app.services.retrieval import run_retrieval
from app.store import Store

SYSTEM_PROMPT = """你是政务政策检索助手。
你只能依据给出的政策片段回答，不得补充片段之外的事实。
如果片段不足，请明确说明“根据当前检索到的政策片段无法确认”。
回答中的每个关键结论后使用 [1]、[2] 这样的编号标注来源。
回答要简洁、准确，并保留必要的办理条件、材料和地点信息。"""


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
                document_title=result.document_title,
                heading_path=result.heading_path,
                page=result.page,
                text=result.text,
            )
        )
    return "\n\n".join(context_parts), citations


async def answer_query(
    store: Store,
    request: AnswerRequest,
    *,
    llm_provider: LLMProvider | None = None,
) -> AnswerResponse:
    chunks = await store.all_chunks(request.chunk_strategy)
    if not chunks:
        raise ValueError("当前切片策略下没有可检索内容")
    run, trace = await asyncio.to_thread(
        run_retrieval,
        chunks=chunks,
        query=request.query,
        strategy=RetrievalStrategy.HYBRID_RERANK,
        chunk_strategy=request.chunk_strategy,
        top_k=request.top_k,
    )
    await store.record_trace(trace)
    provider = llm_provider or get_llm_provider()
    context, citations = build_context(run.results)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"用户问题：{request.query}\n\n检索到的政策片段：\n{context}",
        },
    ]
    answer = await asyncio.to_thread(
        provider.chat,
        messages,
        temperature=request.temperature,
        max_tokens=900,
    )
    return AnswerResponse(
        query=request.query,
        answer=answer,
        model=provider.name,
        retrieval=run,
        citations=citations,
    )
