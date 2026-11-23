import argparse
import asyncio
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import ChunkStrategy, QueryPlanningMode, RetrievalStrategy
from app.services.embedding import get_embedding_provider
from app.services.evaluation_dataset import get_evaluation_dataset
from app.services.llm import get_llm_provider
from app.services.multicondition_dataset import load_multicondition_cases
from app.services.query_planning import QueryPlan, plan_query
from app.services.reranker import BGEReranker
from app.services.retrieval import (
    prepare_dense_scores,
    run_planned_retrieval,
    run_retrieval,
)
from app.store import Store

MODES = (
    QueryPlanningMode.NONE,
    QueryPlanningMode.REWRITE,
    QueryPlanningMode.DECOMPOSE,
)


@dataclass(slots=True)
class CaseRecord:
    mode: str
    case_id: str
    query: str
    rewritten_query: str
    subqueries: list[str]
    retrieval_queries: list[str]
    fallback_reason: str | None
    planner_ms: float
    planner_tokens: int
    retrieval_ms: float
    retrieved_sections: list[str]
    covered_sections: list[str]
    missing_sections: list[str]
    gold_rank: int | None


@dataclass(slots=True)
class ModeSummary:
    mode: str
    recall_at_5: float
    mrr: float
    ndcg_at_5: float
    planner_p95_ms: float
    retrieval_p95_ms: float
    avg_planner_tokens: float
    avg_retrieval_queries: float
    fallbacks: int
    failures: list[str]


@dataclass(slots=True)
class CoverageSummary:
    mode: str
    coverage_rate: float
    full_coverage_rate: float
    planner_p95_ms: float
    retrieval_p95_ms: float
    avg_planner_tokens: float
    avg_retrieval_queries: float
    fallbacks: int
    failures: list[str]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * 0.95) - 1)], 3)


async def _retrieve(
    store: Store,
    chunks,
    *,
    plan: QueryPlan,
    top_k: int,
    reranker: BGEReranker,
):
    if plan.mode is QueryPlanningMode.NONE:
        embedding_provider, dense_scores, dense_latency = await prepare_dense_scores(
            store,
            chunks,
            plan.retrieval_queries[0],
            ChunkStrategy.HEADING,
        )
        return await asyncio.to_thread(
            run_retrieval,
            chunks=chunks,
            query=plan.retrieval_queries[0],
            strategy=RetrievalStrategy.HYBRID_RERANK,
            chunk_strategy=ChunkStrategy.HEADING,
            top_k=top_k,
            embedding_provider=embedding_provider,
            dense_scores_by_chunk=dense_scores,
            precomputed_latency_ms=dense_latency,
            reranker_provider=reranker,
        )
    return await run_planned_retrieval(
        store,
        chunks,
        plan,
        top_k=top_k,
        reranker_provider=reranker,
    )


async def run_benchmark(
    *,
    split: str,
    top_k: int,
    output: Path,
    max_subqueries: int,
) -> int:
    settings = get_settings()
    if settings.store_backend != "postgres":
        raise SystemExit("Query planning benchmark requires STORE_BACKEND=postgres")
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
        seed_official_data=False,
    )
    provider = get_llm_provider()
    reranker = BGEReranker(settings.reranker_model or settings.bge_reranker_model)
    official_cases = get_evaluation_dataset("policy-official-v1", split).cases
    multi_cases = load_multicondition_cases(split)
    records: list[CaseRecord] = []
    summaries: list[ModeSummary] = []
    coverage_summaries: list[CoverageSummary] = []
    try:
        await asyncio.to_thread(reranker.warmup)
        for mode in MODES:
            mode_records: list[CaseRecord] = []
            for case in official_cases:
                chunks = await store.all_chunks(ChunkStrategy.HEADING)
                plan = await plan_query(
                    case.query,
                    mode,
                    llm_provider=provider,
                    max_subqueries=max_subqueries,
                )
                run, _ = await _retrieve(
                    store,
                    chunks,
                    plan=plan,
                    top_k=top_k,
                    reranker=reranker,
                )
                rank = next(
                    (
                        result.rank
                        for result in run.results
                        if result.document_id == case.expected_document_id
                        and case.expected_heading.lower() in result.heading_path.lower()
                    ),
                    None,
                )
                mode_records.append(
                    _record(
                        mode,
                        case.id,
                        case.query,
                        plan,
                        run,
                        expected_sections=(case.expected_heading,),
                        gold_rank=rank,
                    )
                )
            records.extend(mode_records)
            summaries.append(_summarize_official(mode_records))

            multi_records: list[CaseRecord] = []
            for case in multi_cases:
                chunks = await store.all_chunks(ChunkStrategy.HEADING)
                plan = await plan_query(
                    case.query,
                    mode,
                    llm_provider=provider,
                    max_subqueries=max_subqueries,
                )
                run, _ = await _retrieve(
                    store,
                    chunks,
                    plan=plan,
                    top_k=top_k,
                    reranker=reranker,
                )
                first_rank = next(
                    (
                        result.rank
                        for result in run.results
                        if result.document_id == case.expected_document_id
                        and any(
                            section.lower() in result.heading_path.lower()
                            for section in case.expected_sections
                        )
                    ),
                    None,
                )
                multi_records.append(
                    _record(
                        mode,
                        case.id,
                        case.query,
                        plan,
                        run,
                        expected_sections=case.expected_sections,
                        gold_rank=first_rank,
                    )
                )
            records.extend(multi_records)
            coverage_summaries.append(_summarize_coverage(multi_cases, multi_records))
    finally:
        await store.close()

    generated_at = datetime.now(UTC)
    report = _render_report(
        summaries,
        coverage_summaries,
        records,
        generated_at=generated_at,
        split=split,
        official_count=len(official_cases),
        multi_count=len(multi_cases),
        embedding_model=get_embedding_provider().name,
        reranker_model=reranker.name,
        planner_model=provider.name,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "split": split,
                "planner_model": provider.name,
                "embedding_model": get_embedding_provider().name,
                "reranker_model": reranker.name,
                "summaries": [asdict(item) for item in summaries],
                "coverage_summaries": [
                    asdict(item) for item in coverage_summaries
                ],
                "records": [asdict(item) for item in records],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)
    return 0


def _record(
    mode: QueryPlanningMode,
    case_id: str,
    query: str,
    plan: QueryPlan,
    run,
    *,
    expected_sections: tuple[str, ...],
    gold_rank: int | None,
) -> CaseRecord:
    retrieved_sections = [
        f"{result.document_id}::{result.heading_path}" for result in run.results
    ]
    covered = [
        section
        for section in expected_sections
        if any(section.lower() in result.heading_path.lower() for result in run.results)
    ]
    missing = [section for section in expected_sections if section not in covered]
    return CaseRecord(
        mode=mode.value,
        case_id=case_id,
        query=query,
        rewritten_query=plan.rewritten_query,
        subqueries=list(plan.subqueries),
        retrieval_queries=list(plan.retrieval_queries),
        fallback_reason=plan.fallback_reason,
        planner_ms=plan.latency_ms,
        planner_tokens=plan.usage.total_tokens,
        retrieval_ms=run.latency_ms,
        retrieved_sections=retrieved_sections,
        covered_sections=covered,
        missing_sections=missing,
        gold_rank=gold_rank,
    )


def _summarize_official(records: list[CaseRecord]) -> ModeSummary:
    count = max(1, len(records))
    return ModeSummary(
        mode=records[0].mode,
        recall_at_5=round(
            sum(record.gold_rank is not None for record in records) / count,
            4,
        ),
        mrr=round(
            sum(1.0 / record.gold_rank for record in records if record.gold_rank)
            / count,
            4,
        ),
        ndcg_at_5=round(
            sum(
                1.0 / math.log2(record.gold_rank + 1)
                for record in records
                if record.gold_rank
            )
            / count,
            4,
        ),
        planner_p95_ms=_p95([record.planner_ms for record in records]),
        retrieval_p95_ms=_p95([record.retrieval_ms for record in records]),
        avg_planner_tokens=round(
            sum(record.planner_tokens for record in records) / count, 1
        ),
        avg_retrieval_queries=round(
            sum(len(record.retrieval_queries) for record in records) / count, 2
        ),
        fallbacks=sum(record.fallback_reason is not None for record in records),
        failures=[record.case_id for record in records if record.gold_rank is None],
    )


def _summarize_coverage(
    cases,
    records: list[CaseRecord],
) -> CoverageSummary:
    count = max(1, len(records))
    total_sections = sum(len(case.expected_sections) for case in cases)
    covered_sections = sum(len(record.covered_sections) for record in records)
    full = sum(not record.missing_sections for record in records)
    return CoverageSummary(
        mode=records[0].mode,
        coverage_rate=round(covered_sections / max(1, total_sections), 4),
        full_coverage_rate=round(full / count, 4),
        planner_p95_ms=_p95([record.planner_ms for record in records]),
        retrieval_p95_ms=_p95([record.retrieval_ms for record in records]),
        avg_planner_tokens=round(
            sum(record.planner_tokens for record in records) / count, 1
        ),
        avg_retrieval_queries=round(
            sum(len(record.retrieval_queries) for record in records) / count, 2
        ),
        fallbacks=sum(record.fallback_reason is not None for record in records),
        failures=[
            f"{record.case_id}: {','.join(record.missing_sections)}"
            for record in records
            if record.missing_sections
        ],
    )

def _render_report(
    summaries: list[ModeSummary],
    coverage_summaries: list[CoverageSummary],
    records: list[CaseRecord],
    *,
    generated_at: datetime,
    split: str,
    official_count: int,
    multi_count: int,
    embedding_model: str,
    reranker_model: str,
    planner_model: str,
) -> str:
    lines = [
        "# Query Planning Benchmark",
        "",
        f"- Generated: {generated_at.isoformat()}",
        f"- Split: {split}",
        f"- Official answerable cases: {official_count}",
        f"- Multi-condition cases: {multi_count}",
        f"- Planner model: {planner_model}",
        f"- Embedding: {embedding_model}",
        f"- Reranker: {reranker_model}",
        "",
        "## Official answerable set",
        "",
        "| Mode | Recall@5 | MRR | nDCG@5 | Planner P95 | Retrieval P95 | "
        "Avg planner tokens | Avg queries | Fallbacks |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in summaries:
        lines.append(
            f"| {item.mode} | {item.recall_at_5:.4f} | {item.mrr:.4f} | "
            f"{item.ndcg_at_5:.4f} | {item.planner_p95_ms:.1f} ms | "
            f"{item.retrieval_p95_ms:.1f} ms | {item.avg_planner_tokens:.1f} | "
            f"{item.avg_retrieval_queries:.2f} | {item.fallbacks} |"
        )
    lines.extend(
        [
            "",
            "## Multi-condition coverage",
            "",
            "| Mode | Section coverage | Full coverage | Planner P95 | Retrieval P95 | "
            "Avg planner tokens | Avg queries | Fallbacks |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in coverage_summaries:
        lines.append(
            f"| {item.mode} | {item.coverage_rate:.4f} | {item.full_coverage_rate:.4f} | "
            f"{item.planner_p95_ms:.1f} ms | {item.retrieval_p95_ms:.1f} ms | "
            f"{item.avg_planner_tokens:.1f} | {item.avg_retrieval_queries:.2f} | "
            f"{item.fallbacks} |"
        )
    lines.extend(["", "## Failures", ""])
    for item in summaries:
        lines.append(f"### Official · {item.mode}")
        lines.append("")
        lines.append("- " + (", ".join(item.failures) if item.failures else "none"))
        lines.append("")
    for item in coverage_summaries:
        lines.append(f"### Multi-condition · {item.mode}")
        lines.append("")
        lines.append("- " + (", ".join(item.failures) if item.failures else "none"))
        lines.append("")
    lines.extend(
        [
            "## Multi-condition samples",
            "",
            "| Case | Mode | Queries | Covered | Missing |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for record in records:
        if not record.case_id.startswith("multi-"):
            continue
        lines.append(
            f"| `{record.case_id}` | {record.mode} | {len(record.retrieval_queries)} | "
            f"{', '.join(record.covered_sections) or '—'} | "
            f"{', '.join(record.missing_sections) or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Method",
            "",
            "- `none` uses the original query with the production Hybrid + BGE path.",
            "- `rewrite` uses one LLM-rewritten policy query.",
            "- `decompose` runs a rewritten broad query plus limited subqueries, then RRF-fuses "
            "Top candidates.",
            "- Planner timeout or invalid JSON falls back to the original query.",
            "- Development split may be used for prompt iteration; the test split is final-only.",
            "",
            "## Limitations",
            "",
            "- Multi-condition questions are hand-authored and small.",
            "- Query planning adds LLM latency and token cost even when retrieval does not "
            "improve.",
            "- BGE reranking makes answer latency higher than the planner-only latency.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark query planning modes")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="test")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--max-subqueries", type=int, default=4)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/20261124-query-planning-evaluation.md"),
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_benchmark(
                split=args.split,
                top_k=args.top_k,
                output=args.output,
                max_subqueries=args.max_subqueries,
            )
        )
    )


if __name__ == "__main__":
    main()
