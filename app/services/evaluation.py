import asyncio
import math
from datetime import UTC, datetime

from app.schemas import (
    ChunkStrategy,
    EvaluationSummary,
    FailureBucket,
    MetricRow,
    RetrievalStrategy,
)
from app.services.retrieval import STRATEGY_LABELS, run_retrieval
from app.services.seed import EVALUATION_CASES
from app.store import Store


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    return round(ordered[index], 3)


async def evaluate_store(store: Store) -> EvaluationSummary:
    strategies = [
        RetrievalStrategy.DENSE,
        RetrievalStrategy.BM25,
        RetrievalStrategy.HYBRID,
        RetrievalStrategy.HYBRID_RERANK,
    ]
    rows: list[MetricRow] = []
    strategy_latencies: dict[RetrievalStrategy, list[float]] = {
        strategy: [] for strategy in strategies
    }
    strategy_failures: dict[RetrievalStrategy, list[str]] = {
        strategy: [] for strategy in strategies
    }

    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    for strategy in strategies:
        recall = 0.0
        mrr = 0.0
        ndcg = 0.0
        for case in EVALUATION_CASES:
            run, _ = await asyncio.to_thread(
                run_retrieval,
                chunks=chunks,
                query=case.query,
                strategy=strategy,
                chunk_strategy=ChunkStrategy.HEADING,
                top_k=5,
            )
            strategy_latencies[strategy].append(run.latency_ms)
            rank: int | None = None
            for result in run.results:
                if result.document_id != case.expected_document_id:
                    continue
                if case.expected_heading.lower() in result.heading_path.lower():
                    rank = result.rank
                    break
            if rank is None:
                strategy_failures[strategy].append(case.failure_type)
            else:
                recall += 1.0
                mrr += 1.0 / rank
                ndcg += 1.0 / math.log2(rank + 1)
        count = max(1, len(EVALUATION_CASES))
        rows.append(
            MetricRow(
                strategy=strategy,
                label=STRATEGY_LABELS[strategy],
                recall_at_5=round(recall / count, 4),
                mrr=round(mrr / count, 4),
                ndcg_at_5=round(ndcg / count, 4),
                p95_ms=_p95(strategy_latencies[strategy]),
            )
        )

    failure_counter: dict[str, int] = {}
    for failure in strategy_failures[RetrievalStrategy.HYBRID_RERANK]:
        failure_counter[failure] = failure_counter.get(failure, 0) + 1
    failures = [
        FailureBucket(type=failure_type, count=count)
        for failure_type, count in sorted(
            failure_counter.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return EvaluationSummary(
        dataset_name="政策检索演示评测集",
        case_count=len(EVALUATION_CASES),
        rows=rows,
        failures=failures,
        generated_at=datetime.now(UTC),
    )
