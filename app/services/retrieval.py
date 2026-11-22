import asyncio
import math
import time
from collections import Counter
from collections.abc import Mapping
from datetime import UTC, datetime
from uuid import uuid4

from app.schemas import (
    ChunkRecord,
    ChunkStrategy,
    RankDetail,
    RetrievalRun,
    RetrievalStrategy,
    RetrievedChunk,
    TraceRecord,
    TraceStage,
)
from app.services.embedding import EmbeddingProvider, get_embedding_provider
from app.services.text import tokenize
from app.store import Store

STRATEGY_LABELS = {
    RetrievalStrategy.DENSE: "Dense",
    RetrievalStrategy.BM25: "BM25",
    RetrievalStrategy.HYBRID: "Hybrid · RRF",
    RetrievalStrategy.HYBRID_RERANK: "Hybrid · Rerank",
}
class BM25Index:
    def __init__(self, chunks: list[ChunkRecord], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.tokenized = [tokenize(chunk.text) for chunk in chunks]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokenized]
        self.lengths = [len(tokens) for tokens in self.tokenized]
        self.avg_length = sum(self.lengths) / max(1, len(self.lengths))
        document_frequency: Counter[str] = Counter()
        for tokens in self.tokenized:
            document_frequency.update(set(tokens))
        count = max(1, len(chunks))
        self.idf = {
            term: math.log((count - frequency + 0.5) / (frequency + 0.5) + 1)
            for term, frequency in document_frequency.items()
        }

    def scores(self, query: str) -> list[float]:
        query_terms = tokenize(query)
        scores: list[float] = []
        for frequency, length in zip(self.term_frequencies, self.lengths, strict=True):
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * length / max(1, self.avg_length))
            for term in query_terms:
                tf = frequency.get(term, 0)
                if tf:
                    score += self.idf.get(term, 0.0) * tf * (self.k1 + 1) / (tf + norm)
            scores.append(score)
        return scores


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _ranked_indices(scores: list[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda index: scores[index], reverse=True)


def _rrf_fuse(
    dense_ranked: list[int],
    bm25_ranked: list[int],
    k: int = 60,
) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranked in (dense_ranked, bm25_ranked):
        for rank, index in enumerate(ranked, start=1):
            scores[index] = scores.get(index, 0.0) + 1.0 / (k + rank)
    return scores


def _to_result(
    chunk: ChunkRecord,
    score: float,
    rank: int,
    ranks: RankDetail,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.id,
        document_id=chunk.document_id,
        document_title=chunk.document_title,
        page=chunk.page,
        heading_path=chunk.heading_path,
        text=chunk.text,
        score=round(score, 6),
        rank=rank,
        citation=f"{chunk.document_title} · 第{chunk.page}页 · {chunk.heading_path}",
        ranks=ranks,
    )


async def prepare_dense_scores(
    store: Store,
    chunks: list[ChunkRecord],
    query: str,
    strategy: ChunkStrategy,
    embedding_provider: EmbeddingProvider | None = None,
) -> tuple[EmbeddingProvider, dict[str, float] | None, float]:
    provider = embedding_provider or get_embedding_provider()
    started = time.perf_counter()
    query_vector = await asyncio.to_thread(provider.embed_query, query)
    stored = dict(await store.dense_scores(strategy, query_vector))
    latency_ms = (time.perf_counter() - started) * 1000
    if not stored:
        return provider, None, latency_ms
    fallback_score = min(stored.values()) - 0.01
    dense_scores = {
        chunk.id: stored.get(chunk.id, fallback_score)
        for chunk in chunks
    }
    return provider, dense_scores, latency_ms


def run_retrieval(
    chunks: list[ChunkRecord],
    query: str,
    strategy: RetrievalStrategy,
    chunk_strategy: ChunkStrategy,
    top_k: int,
    embedding_provider: EmbeddingProvider | None = None,
    dense_scores_by_chunk: Mapping[str, float] | None = None,
    precomputed_latency_ms: float = 0.0,
) -> tuple[RetrievalRun, TraceRecord]:
    started = time.perf_counter() - precomputed_latency_ms / 1000
    trace_id = f"tr_{uuid4().hex[:10]}"
    stages: list[TraceStage] = []

    query_tokens = tokenize(query)
    stages.append(
        TraceStage(
            key="tokenize",
            label="查询解析",
            duration_ms=0.12,
            output_count=len(query_tokens),
            detail="中文单字 + 二元词组 + 英文词元",
        )
    )

    provider = embedding_provider or get_embedding_provider()
    dense_started = time.perf_counter() - precomputed_latency_ms / 1000
    if dense_scores_by_chunk is not None:
        dense_scores = [dense_scores_by_chunk[chunk.id] for chunk in chunks]
        dense_detail = f"{provider.name}；PostgreSQL pgvector cosine"
    else:
        query_vector = provider.embed_query(query)
        chunk_vectors = provider.embed_documents([chunk.text for chunk in chunks])
        dense_scores = [_cosine(query_vector, vector) for vector in chunk_vectors]
        dense_detail = f"{provider.name}；Provider 实时计算"
    dense_ranked = _ranked_indices(dense_scores)
    dense_rank_map = {index: rank for rank, index in enumerate(dense_ranked, start=1)}
    stages.append(
        TraceStage(
            key="dense",
            label="Dense 召回",
            duration_ms=(time.perf_counter() - dense_started) * 1000,
            input_count=len(chunks),
            output_count=min(20, len(chunks)),
            detail=dense_detail,
        )
    )

    bm25_started = time.perf_counter()
    bm25_index = BM25Index(chunks)
    bm25_scores = bm25_index.scores(query)
    bm25_ranked = _ranked_indices(bm25_scores)
    bm25_rank_map = {index: rank for rank, index in enumerate(bm25_ranked, start=1)}
    stages.append(
        TraceStage(
            key="bm25",
            label="BM25 召回",
            duration_ms=(time.perf_counter() - bm25_started) * 1000,
            input_count=len(chunks),
            output_count=min(20, len(chunks)),
            detail="中文二元词组 BM25，擅长政策编号和精确条款",
        )
    )

    selected: list[RetrievedChunk] = []
    if strategy is RetrievalStrategy.DENSE:
        for rank, index in enumerate(dense_ranked[:top_k], start=1):
            selected.append(
                _to_result(
                    chunks[index],
                    dense_scores[index],
                    rank,
                    RankDetail(dense_rank=rank),
                )
            )
    elif strategy is RetrievalStrategy.BM25:
        for rank, index in enumerate(bm25_ranked[:top_k], start=1):
            selected.append(
                _to_result(
                    chunks[index],
                    bm25_scores[index],
                    rank,
                    RankDetail(bm25_rank=rank),
                )
            )
    else:
        fusion_started = time.perf_counter()
        fused_scores = _rrf_fuse(dense_ranked[:50], bm25_ranked[:50])
        fused_ranked = sorted(fused_scores, key=fused_scores.get, reverse=True)
        fused_rank_map = {index: rank for rank, index in enumerate(fused_ranked, start=1)}
        stages.append(
            TraceStage(
                key="rrf",
                label="RRF 融合",
                duration_ms=(time.perf_counter() - fusion_started) * 1000,
                input_count=min(50, len(chunks)) * 2,
                output_count=min(30, len(fused_ranked)),
                detail="Reciprocal Rank Fusion，k=60，无需手工调整权重",
            )
        )

        if strategy is RetrievalStrategy.HYBRID:
            for rank, index in enumerate(fused_ranked[:top_k], start=1):
                selected.append(
                    _to_result(
                        chunks[index],
                        fused_scores[index],
                        rank,
                        RankDetail(
                            dense_rank=dense_rank_map.get(index),
                            bm25_rank=bm25_rank_map.get(index),
                        ),
                    )
                )
        else:
            rerank_started = time.perf_counter()
            candidates = fused_ranked[:30]
            max_bm25 = max(bm25_scores) if bm25_scores else 1.0
            max_dense = max(dense_scores) if dense_scores else 1.0
            reranked: list[tuple[int, float]] = []
            query_lower = query.lower()
            for index in candidates:
                chunk = chunks[index]
                coverage = (
                    sum(1 for token in set(query_tokens) if token in chunk.text.lower())
                    / max(1, len(set(query_tokens)))
                )
                phrase_bonus = 0.25 if query_lower in chunk.text.lower() else 0.0
                heading_match = any(token in chunk.heading_path.lower() for token in query_tokens)
                heading_bonus = 0.12 if heading_match else 0.0
                score = (
                    0.45 * (bm25_scores[index] / max_bm25)
                    + 0.25 * (dense_scores[index] / max_dense)
                    + 0.18 * coverage
                    + phrase_bonus
                    + heading_bonus
                )
                reranked.append((index, score))
            reranked.sort(key=lambda item: item[1], reverse=True)
            stages.append(
                TraceStage(
                    key="rerank",
                    label="启发式重排",
                    duration_ms=(time.perf_counter() - rerank_started) * 1000,
                    input_count=len(candidates),
                    output_count=min(top_k, len(reranked)),
                    detail="演示重排器；生产环境替换为 BGE Reranker Provider",
                )
            )
            for rank, (index, score) in enumerate(reranked[:top_k], start=1):
                previous_rank = fused_rank_map.get(index, rank)
                selected.append(
                    _to_result(
                        chunks[index],
                        score,
                        rank,
                        RankDetail(
                            dense_rank=dense_rank_map.get(index),
                            bm25_rank=bm25_rank_map.get(index),
                            rerank_delta=previous_rank - rank,
                        ),
                    )
                )

    total_ms = (time.perf_counter() - started) * 1000
    stages.append(
        TraceStage(
            key="finalize",
            label="Context Pack",
            duration_ms=0.18,
            input_count=len(selected),
            output_count=len(selected),
            detail="保留排序、引用与原文定位信息",
        )
    )
    trace = TraceRecord(
        id=trace_id,
        query=query,
        strategy=strategy,
        chunk_strategy=chunk_strategy,
        total_ms=round(total_ms, 3),
        created_at=datetime.now(UTC),
        stages=stages,
    )
    run = RetrievalRun(
        strategy=strategy,
        label=STRATEGY_LABELS[strategy],
        latency_ms=round(total_ms, 3),
        trace_id=trace_id,
        results=selected,
    )
    return run, trace
