import argparse
import asyncio
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import ChunkStrategy, RetrievalFilters, RetrievalStrategy
from app.services.embedding import get_embedding_provider
from app.services.evaluation_dataset import get_evaluation_dataset
from app.services.reranker import BGEReranker
from app.services.retrieval import prepare_dense_scores, run_retrieval


@dataclass(slots=True)
class ModeMetrics:
    name: str
    filters: dict[str, object] | None
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    document_precision_at_5: float
    p95_ms: float
    avg_candidate_count: float
    failures: list[str]
    ranks: dict[str, int | None]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3)


async def _evaluate_mode(
    store: PostgresStore,
    *,
    name: str,
    filters: RetrievalFilters | None,
    dataset_name: str,
    split: str,
    top_k: int,
    reranker: BGEReranker,
) -> ModeMetrics:
    cases = get_evaluation_dataset(dataset_name, split).cases
    latencies: list[float] = []
    candidate_counts: list[float] = []
    failures: list[str] = []
    ranks: dict[str, int | None] = {}
    precision_sum = 0.0
    recall_sum = 0.0
    mrr_sum = 0.0
    ndcg_sum = 0.0

    for case in cases:
        chunks = await store.all_chunks(
            ChunkStrategy.HEADING,
            filters=filters,
        )
        unfiltered_count = (
            await store.count_chunks_for_strategy(ChunkStrategy.HEADING)
            if filters is not None and filters.has_conditions()
            else None
        )
        candidate_counts.append(float(len(chunks)))
        embedding_provider, dense_scores, dense_latency = await prepare_dense_scores(
            store,
            chunks,
            case.query,
            ChunkStrategy.HEADING,
            filters=filters,
        )
        run, _ = await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=case.query,
            strategy=RetrievalStrategy.HYBRID_RERANK,
            chunk_strategy=ChunkStrategy.HEADING,
            top_k=top_k,
            embedding_provider=embedding_provider,
            dense_scores_by_chunk=dense_scores,
            precomputed_latency_ms=dense_latency,
            reranker_provider=reranker,
            filters=filters,
            unfiltered_chunk_count=unfiltered_count,
        )
        latencies.append(run.latency_ms)
        rank = next(
            (
                result.rank
                for result in run.results
                if result.document_id == case.expected_document_id
                and case.expected_heading.lower() in result.heading_path.lower()
            ),
            None,
        )
        ranks[case.id] = rank
        expected_documents = sum(
            result.document_id == case.expected_document_id for result in run.results
        )
        precision_sum += expected_documents / max(1, len(run.results))
        if rank is None:
            failures.append(case.failure_type)
        else:
            recall_sum += 1.0
            mrr_sum += 1.0 / rank
            ndcg_sum += 1.0 / math.log2(rank + 1)

    count = max(1, len(cases))
    return ModeMetrics(
        name=name,
        filters=(
            filters.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            if filters
            else None
        ),
        recall_at_5=round(recall_sum / count, 4),
        mrr=round(mrr_sum / count, 4),
        ndcg_at_5=round(ndcg_sum / count, 4),
        document_precision_at_5=round(precision_sum / count, 4),
        p95_ms=_p95(latencies),
        avg_candidate_count=round(sum(candidate_counts) / count, 1),
        failures=failures,
        ranks=ranks,
    )


def _render_report(
    metrics: list[ModeMetrics],
    *,
    generated_at: datetime,
    dataset_name: str,
    split: str,
    case_count: int,
    embedding_model: str,
    reranker_model: str,
) -> str:
    lines = [
        "# Metadata Filter Benchmark",
        "",
        f"- Generated: {generated_at.isoformat()}",
        f"- Dataset: {dataset_name} / {split}",
        f"- Cases: {case_count}",
        f"- Embedding: {embedding_model}",
        f"- Reranker: {reranker_model}",
        "- Database: isolated evaluation DB containing official guides plus explicitly labeled "
        "outdated and prompt-injection materials",
        "",
        "## Results",
        "",
        "| Mode | Recall@5 | MRR | nDCG@5 | Document P@5 | Avg candidates | P95 | Failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in metrics:
        lines.append(
            f"| {item.name} | {item.recall_at_5:.4f} | {item.mrr:.4f} | "
            f"{item.ndcg_at_5:.4f} | {item.document_precision_at_5:.4f} | "
            f"{item.avg_candidate_count:.1f} | {item.p95_ms:.1f} ms | "
            f"{len(item.failures)} |"
        )
    unfiltered, filtered = metrics[0], metrics[1]
    lines.extend(
        [
            "",
            "## Delta",
            "",
            f"- Recall@5: {filtered.recall_at_5 - unfiltered.recall_at_5:+.4f}",
            f"- MRR: {filtered.mrr - unfiltered.mrr:+.4f}",
            f"- nDCG@5: {filtered.ndcg_at_5 - unfiltered.ndcg_at_5:+.4f}",
            "- Document P@5: "
            f"{filtered.document_precision_at_5 - unfiltered.document_precision_at_5:+.4f}",
            "- Avg candidates: "
            f"{filtered.avg_candidate_count - unfiltered.avg_candidate_count:+.1f}",
            f"- P95: {filtered.p95_ms - unfiltered.p95_ms:+.1f} ms",
            "",
            "## Failures",
            "",
        ]
    )
    for item in metrics:
        lines.append(f"- **{item.name}**: {', '.join(item.failures) or 'none'}")
    lines.extend(
        [
            "",
            "## Method",
            "",
            "- Both modes use Qwen embedding, Hybrid RRF, the same BGE reranker and "
            "Top-5 evaluation.",
            "- Filtered mode applies `region=常州市` and `official_only=true` inside the "
            "repository.",
            "- Retrieval Recall/MRR/nDCG require the expected document and section in Top-5.",
            "- Document precision is the share of returned Top-5 chunks from the expected "
            "document.",
            "- Document ordering uses retrieval time, effective date and update time, newest "
            "first.",
            "",
            "## Limitations",
            "",
            "- Distractor documents are controlled evaluation fixtures, not production traffic.",
            "- The official filter can hide a legitimate newer policy if its metadata is "
            "incomplete.",
            "- Absolute latency includes embedding and rerank network/model costs.",
            "",
        ]
    )
    return "\n".join(lines)


async def run_benchmark(
    *,
    output: Path,
    dataset_name: str,
    split: str,
    top_k: int,
) -> int:
    settings = get_settings()
    if settings.store_backend != "postgres":
        raise SystemExit("Metadata filter benchmark requires STORE_BACKEND=postgres")
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
        seed_official_data=False,
    )
    reranker = BGEReranker(settings.reranker_model or settings.bge_reranker_model)
    try:
        await asyncio.to_thread(reranker.warmup)
        metrics = [
            await _evaluate_mode(
                store,
                name="unfiltered",
                filters=None,
                dataset_name=dataset_name,
                split=split,
                top_k=top_k,
                reranker=reranker,
            ),
            await _evaluate_mode(
                store,
                name="official_filter",
                filters=RetrievalFilters(region="常州市", official_only=True),
                dataset_name=dataset_name,
                split=split,
                top_k=top_k,
                reranker=reranker,
            ),
        ]
    finally:
        await store.close()

    dataset = get_evaluation_dataset(dataset_name, split)
    generated_at = datetime.now(UTC)
    report = _render_report(
        metrics,
        generated_at=generated_at,
        dataset_name=dataset.name,
        split=dataset.split,
        case_count=len(dataset.cases),
        embedding_model=get_embedding_provider().name,
        reranker_model=reranker.name,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "dataset": dataset.name,
                "split": dataset.split,
                "embedding_model": get_embedding_provider().name,
                "reranker_model": reranker.name,
                "metrics": [asdict(item) for item in metrics],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare retrieval with metadata filters")
    parser.add_argument("--dataset", default="policy-official-v1")
    parser.add_argument("--split", default="test", choices=["dev", "test", "all"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/20261124-metadata-filter-evaluation.md"),
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_benchmark(
                output=args.output,
                dataset_name=args.dataset,
                split=args.split,
                top_k=args.top_k,
            )
        )
    )


if __name__ == "__main__":
    main()
