import argparse
import asyncio
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import ChunkStrategy, RetrievalStrategy
from app.services.embedding import EmbeddingProvider
from app.services.llm import get_llm_provider
from app.services.reranker import (
    HeuristicReranker,
    LLMReranker,
    NoneReranker,
    RerankerProvider,
)
from app.services.retrieval import prepare_dense_scores, run_retrieval
from app.services.seed import EVALUATION_CASES, EvaluationCase
from app.store import Store


@dataclass(slots=True)
class PreparedCase:
    case: EvaluationCase
    embedding_provider: EmbeddingProvider
    dense_scores: dict[str, float] | None
    dense_latency_ms: float


@dataclass(slots=True)
class ProviderMetrics:
    name: str
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    p95_ms: float
    failures: list[str]
    fallback_count: int


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)]


def _provider(name: str) -> RerankerProvider:
    if name == "heuristic":
        return HeuristicReranker()
    if name == "none":
        return NoneReranker()
    if name == "llm":
        return LLMReranker(get_llm_provider())
    raise ValueError(f"未知 Reranker Provider：{name}")


async def prepare_cases(store: Store) -> list[PreparedCase]:
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    prepared: list[PreparedCase] = []
    for case in EVALUATION_CASES:
        embedding_provider, dense_scores, dense_latency = await prepare_dense_scores(
            store,
            chunks,
            case.query,
            ChunkStrategy.HEADING,
        )
        prepared.append(
            PreparedCase(
                case=case,
                embedding_provider=embedding_provider,
                dense_scores=dense_scores,
                dense_latency_ms=dense_latency,
            )
        )
    return prepared


async def evaluate_provider(
    store: Store,
    provider: RerankerProvider,
    prepared_cases: Sequence[PreparedCase],
) -> ProviderMetrics:
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    latencies: list[float] = []
    failures: list[str] = []
    recall = 0.0
    mrr = 0.0
    ndcg = 0.0
    fallback_count = 0

    for prepared in prepared_cases:
        case = prepared.case
        run, trace = await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=case.query,
            strategy=RetrievalStrategy.HYBRID_RERANK,
            chunk_strategy=ChunkStrategy.HEADING,
            top_k=5,
            embedding_provider=prepared.embedding_provider,
            dense_scores_by_chunk=prepared.dense_scores,
            precomputed_latency_ms=prepared.dense_latency_ms,
            reranker_provider=provider,
        )
        latencies.append(run.latency_ms)
        if provider.name.startswith("llm ·"):
            await asyncio.sleep(10.0)
        rerank_stage = next(stage for stage in trace.stages if stage.key == "rerank")
        if "降级" in rerank_stage.detail:
            fallback_count += 1

        rank = next(
            (
                result.rank
                for result in run.results
                if result.document_id == case.expected_document_id
                and case.expected_heading.lower() in result.heading_path.lower()
            ),
            None,
        )
        if rank is None:
            failures.append(case.id)
            continue
        recall += 1.0
        mrr += 1.0 / rank
        ndcg += 1.0 / math.log2(rank + 1)

    count = max(1, len(EVALUATION_CASES))
    return ProviderMetrics(
        name=provider.name,
        recall_at_5=recall / count,
        mrr=mrr / count,
        ndcg_at_5=ndcg / count,
        p95_ms=_p95(latencies),
        failures=failures,
        fallback_count=fallback_count,
    )


def render_report(metrics: Sequence[ProviderMetrics], generated_at: datetime) -> str:
    baseline = metrics[0]
    lines = [
        "# Reranker Comparison",
        "",
        f"- Generated: {generated_at.isoformat()}",
        f"- Dataset cases: {len(EVALUATION_CASES)}",
        "- Dataset source: `app/services/seed.py::EVALUATION_CASES`",
        "- Strategy: Hybrid RRF + Top-30 candidate reranking + Top-5 evaluation",
        "",
        "## Results",
        "",
        "| Provider | Recall@5 | MRR | nDCG@5 | P95 | ΔMRR vs baseline | Fallbacks |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in metrics:
        lines.append(
            f"| {item.name} | {item.recall_at_5:.4f} | {item.mrr:.4f} | "
            f"{item.ndcg_at_5:.4f} | {item.p95_ms:.1f} ms | "
            f"{item.mrr - baseline.mrr:+.4f} | {item.fallback_count} |"
        )
    fallback_total = sum(item.fallback_count for item in metrics)
    if fallback_total:
        lines.extend(
            [
                "",
                f"> INVALID RESULT: {fallback_total} reranker calls fell back. "
                "Do not cite these metrics until the run has zero fallbacks.",
            ]
        )
    lines.extend(["", "## Failures", ""])
    for item in metrics:
        failed = ", ".join(item.failures) if item.failures else "none"
        lines.append(f"- **{item.name}**: {failed}")
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This is the internal 10-case demonstration set, not the final 150-case benchmark.",
            "- Token usage and monetary cost are not yet recorded by the shared LLM provider.",
            "- A non-zero fallback count means reranker errors affected the measured result.",
            "",
        ]
    )
    return "\n".join(lines)


async def run_benchmark(provider_names: Sequence[str], output: Path | None) -> int:
    settings = get_settings()
    if settings.store_backend != "postgres":
        raise SystemExit("Reranker benchmark requires STORE_BACKEND=postgres")
    store = await PostgresStore.create(settings.database_url, seed_demo_data=False)
    try:
        provider_list = [_provider(name) for name in provider_names]
        prepared_cases = await prepare_cases(store)
        metrics = [
            await evaluate_provider(store, provider, prepared_cases)
            for provider in provider_list
        ]
    finally:
        await store.close()

    generated_at = datetime.now(UTC)
    report = render_report(metrics, generated_at)
    if output is None:
        stamp = generated_at.strftime("%Y%m%d-%H%M%S")
        output = Path("docs/experiments") / f"{stamp}-reranker-comparison.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report)
    print(report)
    return 1 if any(item.fallback_count for item in metrics) else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare reranker providers on the evaluation set")
    parser.add_argument(
        "--providers",
        default="heuristic,none",
        help="Comma-separated provider order; first item is the baseline",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    providers = [name.strip() for name in args.providers.split(",") if name.strip()]
    raise SystemExit(asyncio.run(run_benchmark(providers, args.output)))


if __name__ == "__main__":
    main()
