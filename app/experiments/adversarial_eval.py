import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import AnswerRequest, ChunkStrategy, RetrievalFilters
from app.services.adversarial_eval import (
    AdversarialCase,
    load_adversarial_cases,
    score_adversarial_answer,
)
from app.services.answer import answer_query
from app.services.embedding import get_embedding_provider
from app.services.llm import get_llm_provider
from app.services.reranker import get_reranker_provider

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "data" / "eval" / "adversarial" / "corpus"


@dataclass(slots=True)
class CaseRun:
    id: str
    query: str
    category: str
    expected_behavior: str
    notes: str
    answer: str
    trace_id: str
    retrieval_document_ids: list[str]
    citations: list[dict[str, object]]
    invalid_citation_ids: list[int]
    abstained: bool
    required_missing: list[str]
    forbidden_hits: list[str]
    unsafe_forbidden_hits: list[str]
    refutation_detected: bool
    system_prompt_leak: bool
    injection_exposed: bool
    leak_detected: bool
    passed: bool
    false_answer: bool
    answer_ms: float
    answer_error: str | None
    trace: dict[str, object] | None


async def _ensure_adversarial_corpus(store: PostgresStore) -> dict[str, str]:
    existing = {document.title: document.id for document in await store.list_documents()}
    corpus_ids: dict[str, str] = {}
    for path in sorted(CORPUS_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        title = next(
            line.removeprefix("# ").strip()
            for line in content.splitlines()
            if line.startswith("# ")
        )
        if title not in existing:
            document = await store.add_upload(
                path.name,
                content.encode("utf-8"),
                title=title,
                department="PolicyRAG Safety Eval",
            )
            existing[title] = document.id
        corpus_ids[path.name] = existing[title]
    return corpus_ids


async def _run_case(
    store: PostgresStore,
    case: AdversarialCase,
    *,
    top_k: int,
    semaphore: asyncio.Semaphore,
    injection_document_ids: set[str],
    filters: RetrievalFilters | None,
) -> CaseRun:
    async with semaphore:
        try:
            response = await answer_query(
                store,
                AnswerRequest(
                    query=case.query,
                    chunk_strategy=ChunkStrategy.HEADING,
                    top_k=top_k,
                    filters=filters,
                ),
            )
        except Exception as error:  # noqa: BLE001 - retain per-case evidence
            return CaseRun(
                id=case.id,
                query=case.query,
                category=case.category,
                expected_behavior=case.expected_behavior,
                notes=case.notes,
                answer="",
                trace_id="",
                retrieval_document_ids=[],
                citations=[],
                invalid_citation_ids=[],
                abstained=False,
                required_missing=list(case.required_terms),
                forbidden_hits=[],
                unsafe_forbidden_hits=[],
                refutation_detected=False,
                system_prompt_leak=False,
                injection_exposed=False,
                leak_detected=False,
                passed=False,
                false_answer=True,
                answer_ms=0.0,
                answer_error=f"{type(error).__name__}: {error}",
                trace=None,
            )

        outcome = score_adversarial_answer(
            case,
            response.answer,
            invalid_citation_ids=response.invalid_citation_ids,
        )
        trace = await store.get_trace(response.retrieval.trace_id)
        retrieval_document_ids = [
            result.document_id for result in response.retrieval.results
        ]
        return CaseRun(
            id=case.id,
            query=case.query,
            category=case.category,
            expected_behavior=case.expected_behavior,
            notes=case.notes,
            answer=response.answer,
            trace_id=response.retrieval.trace_id,
            retrieval_document_ids=retrieval_document_ids,
            citations=[citation.model_dump(mode="json") for citation in response.citations],
            invalid_citation_ids=response.invalid_citation_ids,
            abstained=outcome.abstained,
            required_missing=list(outcome.required_missing),
            forbidden_hits=list(outcome.forbidden_hits),
            unsafe_forbidden_hits=list(outcome.unsafe_forbidden_hits),
            refutation_detected=outcome.refutation_detected,
            system_prompt_leak=outcome.system_prompt_leak,
            injection_exposed=bool(
                injection_document_ids.intersection(retrieval_document_ids)
            ),
            leak_detected=outcome.leak_detected,
            passed=outcome.passed,
            false_answer=outcome.false_answer,
            answer_ms=response.total_ms or 0.0,
            answer_error=None,
            trace=trace.model_dump(mode="json") if trace else None,
        )


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _summarize(results: list[CaseRun]) -> dict[str, object]:
    total = len(results)
    abstraction_cases = [r for r in results if r.expected_behavior == "abstain"]
    injection_cases = [r for r in results if r.category == "prompt_injection"]
    invalid_citation_cases = [r for r in results if r.invalid_citation_ids]
    answered = [r for r in results if not r.answer_error]
    return {
        "case_count": total,
        "passed": sum(r.passed for r in results),
        "pass_rate": round(sum(r.passed for r in results) / max(1, total), 4),
        "false_answers": sum(r.false_answer for r in results),
        "false_answer_rate": round(sum(r.false_answer for r in results) / max(1, total), 4),
        "expected_abstention_cases": len(abstraction_cases),
        "correct_abstentions": sum(r.passed for r in abstraction_cases),
        "abstention_rate": round(
            sum(r.passed for r in abstraction_cases) / max(1, len(abstraction_cases)), 4
        ),
        "prompt_injection_cases": len(injection_cases),
        "prompt_injection_exposed": sum(r.injection_exposed for r in injection_cases),
        "prompt_injection_leaks": sum(r.leak_detected for r in injection_cases),
        "prompt_injection_leak_rate": round(
            sum(r.leak_detected for r in injection_cases) / max(1, len(injection_cases)), 4
        ),
        "invalid_citation_cases": len(invalid_citation_cases),
        "invalid_citation_rate": round(
            len(invalid_citation_cases) / max(1, total), 4
        ),
        "answer_errors": total - len(answered),
        "avg_answer_ms": round(
            sum(r.answer_ms for r in answered) / max(1, len(answered)), 1
        ),
    }


def _render_report(
    results: list[CaseRun],
    summary: dict[str, object],
    *,
    generated_at: datetime,
    corpus_ids: dict[str, str],
    embedding_model: str,
    reranker_model: str,
    answer_model: str,
    filters: RetrievalFilters | None,
) -> str:
    pass_rate = _percent(summary["pass_rate"])
    false_rate = _percent(summary["false_answer_rate"])
    abstention_rate = _percent(summary["abstention_rate"])
    leak_rate = _percent(summary["prompt_injection_leak_rate"])
    invalid_cite_rate = _percent(summary["invalid_citation_rate"])
    lines = [
        "# Adversarial Grounding Evaluation",
        "",
        f"- Generated: {generated_at.isoformat()}",
        "- Dataset: `policy-adversarial-v1` / test",
        f"- Cases: {summary['case_count']}",
        f"- Embedding: {embedding_model}",
        f"- Reranker: {reranker_model}",
        f"- Answer model: {answer_model}",
        f"- Filters: {filters.trace_detail() if filters else 'none'}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Correct behavior | {summary['passed']} / {summary['case_count']} ({pass_rate}) |",
        f"| False answers | {summary['false_answers']} ({false_rate}) |",
        f"| Expected abstention cases | {summary['expected_abstention_cases']} |",
        f"| Correct abstention rate | {abstention_rate} |",
        f"| Prompt-injection cases | {summary['prompt_injection_cases']} |",
        f"| Injection material exposed | {summary['prompt_injection_exposed']} |",
        f"| Prompt-injection leaks | {summary['prompt_injection_leaks']} ({leak_rate}) |",
        f"| Invalid citation cases | {summary['invalid_citation_cases']} ({invalid_cite_rate}) |",
        f"| Answer errors | {summary['answer_errors']} |",
        f"| Avg answer latency | {summary['avg_answer_ms']:.1f} ms |",
        "",
        "## Cases",
        "",
        "| Case | Category | Expected | Result | Abstained | Mentioned | Unsafe | Invalid cites |",
        "| --- | --- | --- | :---: | :---: | --- | --- | --- |",
    ]
    for result in results:
        lines.append(
            f"| `{result.id}` | {result.category} | {result.expected_behavior} | "
            f"{'✓' if result.passed else '✗'} | {'✓' if result.abstained else '✗'} | "
            f"{', '.join(result.forbidden_hits) or '—'} | "
            f"{', '.join(result.unsafe_forbidden_hits) or '—'} | "
            f"{result.invalid_citation_ids or '—'} |"
        )
    lines.extend(["", "## Answers and failures", ""])
    for result in results:
        if result.passed and not result.false_answer:
            continue
        lines.extend(
            [
                f"### `{result.id}` — {result.category}",
                "",
                f"Question: {result.query}",
                "",
                f"Expected: `{result.expected_behavior}`; notes: {result.notes}",
                "",
                f"Answer: {result.answer or result.answer_error or 'empty'}",
                "",
                f"Missing required terms: {result.required_missing or 'none'}",
                f"Forbidden mentions: {result.forbidden_hits or 'none'}",
                f"Unsafe forbidden claims: {result.unsafe_forbidden_hits or 'none'}",
                f"Refutation context detected: {result.refutation_detected}",
                f"System prompt leak: {result.system_prompt_leak}",
                f"Invalid citations: {result.invalid_citation_ids or 'none'}",
                f"Trace: `{result.trace_id or 'none'}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Corpus",
            "",
        ]
    )
    for name, document_id in sorted(corpus_ids.items()):
        lines.append(f"- `{name}` -> `{document_id}`")
    lines.extend(
        [
            "",
            "## Method",
            "",
            "- Answers use the production path: Hybrid retrieval -> rerank -> context -> "
            "LLM -> citation guard.",
            "- Expected `abstain` cases require an explicit refusal and reject unsafe "
            "forbidden claims.",
            "- Claims quoted only to identify and reject older or malicious material are "
            "recorded separately.",
            "- Expected `answer` cases require all current-policy terms and reject claims "
            "from the outdated test guide.",
            "- Prompt-injection leak checks look for exact injected claims and system-prompt "
            "signatures.",
            "- This is a bounded adversarial set, not a guarantee against all prompt injection.",
            "",
            "## Limitations",
            "",
            "- Safety labels are hand-authored; deterministic checks cannot judge every "
            "semantic refusal.",
            "- The answer model may retrieve or ignore adversarial material; exposure is "
            "reported separately.",
            "- Real model calls can be rate-limited; failed calls remain as failures.",
            "",
        ]
    )
    return "\n".join(lines)


async def run_evaluation(
    *,
    output: Path,
    concurrency: int,
    top_k: int,
    filters: RetrievalFilters | None = None,
) -> int:
    settings = get_settings()
    if settings.store_backend != "postgres":
        raise SystemExit("Adversarial evaluation requires STORE_BACKEND=postgres")
    cases = load_adversarial_cases()
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
        seed_official_data=False,
    )
    try:
        corpus_ids = await _ensure_adversarial_corpus(store)
        injection_ids = {
            corpus_ids["prompt-injection-subsidy.md"]
            if "prompt-injection-subsidy.md" in corpus_ids
            else ""
        }
        injection_ids.discard("")
        semaphore = asyncio.Semaphore(max(1, concurrency))
        results = list(
            await asyncio.gather(
                *[
                    _run_case(
                        store,
                        case,
                        top_k=top_k,
                        semaphore=semaphore,
                        injection_document_ids=injection_ids,
                        filters=filters,
                    )
                    for case in cases
                ]
            )
        )
    finally:
        await store.close()

    summary = _summarize(results)
    generated_at = datetime.now(UTC)
    report = _render_report(
        results,
        summary,
        generated_at=generated_at,
        corpus_ids=corpus_ids,
        embedding_model=get_embedding_provider().name,
        reranker_model=get_reranker_provider().name,
        answer_model=get_llm_provider().name,
        filters=filters,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "summary": summary,
                "filters": (
                    filters.model_dump(mode="json", exclude_none=True)
                    if filters
                    else None
                ),
                "results": [asdict(result) for result in results],
                "corpus_ids": corpus_ids,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)
    return 0 if summary["false_answers"] == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run adversarial grounding evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/20261124-adversarial-evaluation.md"),
    )
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--official-only", action="store_true")
    parser.add_argument("--region")
    parser.add_argument("--item-type")
    parser.add_argument("--department")
    args = parser.parse_args()
    filters = RetrievalFilters(
        region=args.region,
        item_type=args.item_type,
        department=args.department,
        official_only=args.official_only,
    )
    if not filters.has_conditions():
        filters = None
    raise SystemExit(
        asyncio.run(
            run_evaluation(
                output=args.output,
                concurrency=args.concurrency,
                top_k=args.top_k,
                filters=filters,
            )
        )
    )


if __name__ == "__main__":
    main()
