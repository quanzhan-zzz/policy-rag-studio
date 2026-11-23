"""Answer quality evaluation for the policy RAG pipeline.

Runs the production answer path (Hybrid + Rerank -> context pack -> LLM), then
computes deterministic citation metrics and an optional LLM-as-judge review.
The output is a Markdown report, a raw JSON artifact, and a human review sheet.
"""

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.db.postgres import PostgresStore
from app.schemas import AnswerRequest, AnswerResponse, ChunkStrategy
from app.services.answer import CITATION_PATTERN, answer_query
from app.services.embedding import get_embedding_provider
from app.services.evaluation_dataset import get_evaluation_dataset
from app.services.llm import LLMProvider, LLMProviderError, LLMRateLimitError, get_llm_provider
from app.services.reranker import get_reranker_provider
from app.services.seed import EvaluationCase
from app.store import Store

JUDGE_SYSTEM_PROMPT = """你是严格的政策问答质量评审。
你只根据题目、检索证据和模型回答进行判断，不补充任何外部知识。
必须输出一个 JSON 对象，不要输出 Markdown 代码块或其他文字。
字段：
- faithfulness: 1-5 整数，回答是否完全由证据支持
- relevance: 1-5 整数，回答是否切题
- completeness: 1-5 整数，是否覆盖问题所需的关键条件
- citation_support: "supported" | "partial" | "unsupported"
- unsupported_claims: 字符串数组，列出没有证据支持的结论
- pass: true/false
- reason: 一句话说明
判定标准：faithfulness >= 4 且 relevance >= 4 且 citation_support != "unsupported"
且 unsupported_claims 为空时，pass 才能为 true。"""


@dataclass(slots=True)
class JudgeScore:
    faithfulness: int
    relevance: int
    completeness: int
    citation_support: str
    unsupported_claims: list[str]
    passed: bool
    reason: str


@dataclass(slots=True)
class EvidenceExcerpt:
    source_id: int
    document_id: str
    document_title: str
    heading_path: str
    page: int
    text: str


@dataclass(slots=True)
class CaseResult:
    case_id: str
    query: str
    expected_heading: str
    trace_id: str
    reranker_detail: str
    retrieval_hit: bool
    gold_rank: int | None
    answer: str
    citation_precision: float
    citation_recall: float
    cited_source_ids: list[int]
    cited_evidence: list[EvidenceExcerpt]
    invalid_citation_ids: list[int]
    grounding_status: str
    answer_ms: float
    total_tokens: int
    judge: JudgeScore | None
    judge_error: str | None
    answer_error: str | None


def _clamp_score(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 1
    return min(5, max(1, number))


def parse_judge_payload(raw: str) -> JudgeScore:
    """Parse a judge response, tolerating code fences or surrounding prose."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("judge response does not contain a JSON object")
    payload = json.loads(match.group(0))
    faithfulness = _clamp_score(payload.get("faithfulness"))
    relevance = _clamp_score(payload.get("relevance"))
    completeness = _clamp_score(payload.get("completeness"))
    support = str(payload.get("citation_support", "unsupported")).lower()
    if support not in {"supported", "partial", "unsupported"}:
        support = "unsupported"
    unsupported = payload.get("unsupported_claims") or []
    if not isinstance(unsupported, list):
        unsupported = [str(unsupported)]
    unsupported_claims = [str(item) for item in unsupported if str(item).strip()]
    passed = (
        faithfulness >= 4
        and relevance >= 4
        and support != "unsupported"
        and not unsupported_claims
    )
    return JudgeScore(
        faithfulness=faithfulness,
        relevance=relevance,
        completeness=completeness,
        citation_support=support,
        unsupported_claims=unsupported_claims,
        passed=passed,
        reason=str(payload.get("reason", "")).strip(),
    )


def is_gold_citation(citation: Any, case: EvaluationCase) -> bool:
    return (
        citation.document_id == case.expected_document_id
        and case.expected_heading.lower() in citation.heading_path.lower()
    )


def score_citations(
    response: AnswerResponse,
    case: EvaluationCase,
) -> tuple[float, float, list[int], list[int]]:
    """Return (precision, recall, cited valid ids, invalid ids)."""
    referenced = {int(value) for value in CITATION_PATTERN.findall(response.answer)}
    valid = {citation.source_id for citation in response.citations}
    cited_valid = sorted(referenced & valid)
    invalid = sorted(referenced - valid)
    if not cited_valid:
        return 0.0, 0.0, [], invalid
    matched = [
        citation
        for citation in response.citations
        if citation.source_id in referenced and is_gold_citation(citation, case)
    ]
    return len(matched) / len(cited_valid), 1.0 if matched else 0.0, cited_valid, invalid


def build_judge_messages(case: EvaluationCase, response: AnswerResponse) -> list[dict[str, str]]:
    evidence = "\n\n".join(
        f"[{citation.source_id}] {citation.document_title} · {citation.heading_path} "
        f"· 第{citation.page}页\n{citation.text}"
        for citation in response.citations
    )
    user_prompt = f"""用户问题：
{case.query}

检索证据：
{evidence}

模型回答：
{response.answer}

请按系统要求输出 JSON。"""
    return [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


async def call_with_retry(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    *,
    attempts: int = 4,
    max_tokens: int = 700,
) -> str:
    delay = 4.0
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(
                provider.chat,
                messages,
                temperature=0.0,
                max_tokens=max_tokens,
            )
        except LLMRateLimitError as error:
            last_error = error
            wait = max(error.retry_after_seconds, delay)
        except LLMProviderError as error:
            last_error = error
            wait = delay
        if attempt < attempts - 1:
            await asyncio.sleep(wait)
            delay *= 2
    raise last_error or RuntimeError("LLM call failed without an error")


async def answer_with_retry(
    store: Store,
    case: EvaluationCase,
    provider: LLMProvider,
    *,
    top_k: int,
    attempts: int = 3,
) -> AnswerResponse:
    delay = 4.0
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return await answer_query(
                store,
                AnswerRequest(
                    query=case.query,
                    chunk_strategy=ChunkStrategy.HEADING,
                    top_k=top_k,
                ),
                llm_provider=provider,
            )
        except LLMProviderError as error:
            last_error = error
            if attempt < attempts - 1:
                await asyncio.sleep(delay)
                delay *= 2
    raise last_error or RuntimeError("answer generation failed without an error")


async def evaluate_case(
    store: Store,
    case: EvaluationCase,
    provider: LLMProvider,
    *,
    top_k: int,
    judge_enabled: bool,
    semaphore: asyncio.Semaphore,
) -> CaseResult:
    async with semaphore:
        try:
            response = await answer_with_retry(store, case, provider, top_k=top_k)
        except Exception as error:  # noqa: BLE001 - record per-case failures
            return CaseResult(
                case_id=case.id,
                query=case.query,
                expected_heading=case.expected_heading,
                trace_id="",
                reranker_detail="not_started",
                retrieval_hit=False,
                gold_rank=None,
                answer="",
                citation_precision=0.0,
                citation_recall=0.0,
                cited_source_ids=[],
                cited_evidence=[],
                invalid_citation_ids=[],
                grounding_status="not_generated",
                answer_ms=0.0,
                total_tokens=0,
                judge=None,
                judge_error=None,
                answer_error=f"{type(error).__name__}: {error}",
            )

        gold_rank = next(
            (
                result.rank
                for result in response.retrieval.results
                if result.document_id == case.expected_document_id
                and case.expected_heading.lower() in result.heading_path.lower()
            ),
            None,
        )
        trace = await store.get_trace(response.retrieval.trace_id)
        reranker_detail = next(
            (stage.detail for stage in trace.stages if stage.key == "rerank"),
            "unknown",
        ) if trace else "unknown"
        precision, recall, cited_valid, invalid = score_citations(response, case)
        cited_evidence = [
            EvidenceExcerpt(
                source_id=citation.source_id,
                document_id=citation.document_id,
                document_title=citation.document_title,
                heading_path=citation.heading_path,
                page=citation.page,
                text=citation.text,
            )
            for citation in response.citations
            if citation.source_id in cited_valid
        ]
        judge: JudgeScore | None = None
        judge_error: str | None = None
        if judge_enabled:
            try:
                raw = await call_with_retry(provider, build_judge_messages(case, response))
                judge = parse_judge_payload(raw)
            except Exception as error:  # noqa: BLE001 - keep the report complete
                judge_error = f"{type(error).__name__}: {error}"

        return CaseResult(
            case_id=case.id,
            query=case.query,
            expected_heading=case.expected_heading,
            trace_id=response.retrieval.trace_id,
            reranker_detail=reranker_detail,
            retrieval_hit=gold_rank is not None,
            gold_rank=gold_rank,
            answer=response.answer,
            citation_precision=round(precision, 4),
            citation_recall=round(recall, 4),
            cited_source_ids=cited_valid,
            cited_evidence=cited_evidence,
            invalid_citation_ids=invalid,
            grounding_status=response.grounding_status or "unknown",
            answer_ms=response.total_ms or 0.0,
            total_tokens=response.total_tokens or 0,
            judge=judge,
            judge_error=judge_error,
            answer_error=None,
        )


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    answered = [result for result in results if not result.answer_error]
    judged = [result for result in answered if result.judge]
    return {
        "case_count": len(results),
        "answered": len(answered),
        "answer_errors": len(results) - len(answered),
        "retrieval_hit_rate": round(
            _average([float(result.retrieval_hit) for result in answered]), 4
        ),
        "citation_precision": round(
            _average([result.citation_precision for result in answered]), 4
        ),
        "citation_recall": round(
            _average([result.citation_recall for result in answered]), 4
        ),
        "invalid_citation_rate": round(
            _average([float(bool(result.invalid_citation_ids)) for result in answered]), 4
        ),
        "grounding_supported_rate": round(
            _average([float(result.grounding_status == "supported") for result in answered]), 4
        ),
        "reranker_fallbacks": sum(
            "降级" in result.reranker_detail for result in answered
        ),
        "judged": len(judged),
        "judge_errors": len(answered) - len(judged),
        "judge_pass_rate": round(_average([float(result.judge.passed) for result in judged]), 4)
        if judged
        else None,
        "avg_faithfulness": round(
            _average([float(result.judge.faithfulness) for result in judged]), 2
        )
        if judged
        else None,
        "avg_relevance": round(
            _average([float(result.judge.relevance) for result in judged]), 2
        )
        if judged
        else None,
        "avg_completeness": round(
            _average([float(result.judge.completeness) for result in judged]), 2
        )
        if judged
        else None,
        "avg_answer_ms": round(_average([result.answer_ms for result in answered]), 1),
        "avg_total_tokens": round(_average([float(result.total_tokens) for result in answered]), 1),
    }


def _format_percent(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _format_score(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def render_report(
    results: list[CaseResult],
    summary: dict[str, Any],
    *,
    generated_at: datetime,
    dataset_name: str,
    split: str,
    answer_model: str,
    judge_model: str | None,
    judge_enabled: bool,
    embedding_model: str,
    reranker_model: str,
    top_k: int,
    review_size: int,
) -> str:
    lines = [
        "# Answer Quality Report",
        "",
        f"- Generated: {generated_at.isoformat()}",
        f"- Dataset: {dataset_name} / {split}",
        f"- Cases: {summary['case_count']}",
        f"- Embedding: {embedding_model}",
        f"- Reranker: {reranker_model}",
        f"- Answer model: {answer_model}",
        f"- Judge model: {judge_model if judge_enabled else 'disabled'}",
        f"- Human review: {review_size}-case worksheet generated; pending manual completion",
        "- Path: Hybrid + Rerank -> Context Pack -> answer -> citation metrics/judge",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Answered | {summary['answered']} / {summary['case_count']} |",
        f"| Retrieval Hit@{top_k} | {_format_percent(summary['retrieval_hit_rate'])} |",
        f"| Citation precision | {_format_percent(summary['citation_precision'])} |",
        f"| Citation recall | {_format_percent(summary['citation_recall'])} |",
        f"| Invalid citation rate | {_format_percent(summary['invalid_citation_rate'])} |",
        f"| Grounding supported | {_format_percent(summary['grounding_supported_rate'])} |",
        f"| Reranker fallbacks | {summary['reranker_fallbacks']} |",
        f"| LLM judge pass rate | {_format_percent(summary['judge_pass_rate'])} |",
        f"| LLM faithfulness (1-5) | {_format_score(summary['avg_faithfulness'])} |",
        f"| LLM relevance (1-5) | {_format_score(summary['avg_relevance'])} |",
        f"| LLM completeness (1-5) | {_format_score(summary['avg_completeness'])} |",
        f"| Avg answer latency | {summary['avg_answer_ms']:.1f} ms |",
        f"| Avg tokens | {summary['avg_total_tokens']:.0f} |",
        "",
        "## Per-case results",
        "",
        "| Case | Hit@5 | Cite P | Cite R | Grounding | F/R/C | Pass |",
        "| --- | :---: | ---: | ---: | --- | --- | :---: |",
    ]
    for result in results:
        if result.answer_error:
            lines.append(f"| `{result.case_id}` | — | — | — | error | — | ✗ |")
            continue
        judge_scores = (
            f"{result.judge.faithfulness}/{result.judge.relevance}/{result.judge.completeness}"
            if result.judge
            else "—"
        )
        passed = "✓" if result.judge and result.judge.passed else "✗" if result.judge else "—"
        lines.append(
            f"| `{result.case_id}` | {'✓' if result.retrieval_hit else '✗'} | "
            f"{result.citation_precision:.2f} | {result.citation_recall:.0f} | "
            f"{result.grounding_status} | {judge_scores} | {passed} |"
        )

    failures = [
        result
        for result in results
        if (
            result.answer_error
            or not result.retrieval_hit
                or "降级" in result.reranker_detail
            or (result.judge and not result.judge.passed)
        )
    ]
    lines.extend(["", "## Failures and warnings", ""])
    if not failures:
        lines.append("- none")
    for result in failures:
        reasons: list[str] = []
        if result.answer_error:
            reasons.append(f"answer error: {result.answer_error}")
        if not result.retrieval_hit:
            reasons.append("gold chunk missing from Top-5")
        if "降级" in result.reranker_detail:
            reasons.append(f"reranker fallback: {result.reranker_detail}")
        if result.judge and not result.judge.passed:
            reasons.append(
                "judge: " + (result.judge.reason or ", ".join(result.judge.unsupported_claims))
            )
        if result.invalid_citation_ids:
            reasons.append(f"invalid citations: {result.invalid_citation_ids}")
        lines.append(f"- `{result.case_id}` — {result.query} — {'; '.join(reasons)}")
    judge_error_rows = [result for result in results if result.judge_error]
    if judge_error_rows:
        lines.extend(["", "Judge errors:", ""])
        for result in judge_error_rows:
            lines.append(f"- `{result.case_id}` — {result.judge_error}")

    lines.extend(
        [
            "",
            "## Method",
            "",
            "- Citation precision = cited sources matching the gold document + heading / "
            "all valid cited sources.",
            "- Citation recall = 1 when at least one gold source is cited, otherwise 0 (per case).",
            "- Grounding status comes from the production citation guard.",
            "- Reranker fallbacks are read from the persisted retrieval Trace.",
            "- The LLM judge sees the same evidence pack as the answer model, with faithfulness, "
            "relevance and completeness scored 1-5.",
            "- The grader is the configured chat provider; self-evaluation bias is possible.",
            "",
            "## Limitations",
            "",
            f"- The dataset is synthetic and small ({summary['case_count']} cases); absolute "
            "scores are not production claims.",
            "- The judge is the same model family as the answer model. Cross-model judging is "
            "recommended.",
            f"- A {review_size}-case human review sheet is generated next to this report; fill "
            "it before citing results.",
            "- Token counts come from the provider response; monetary cost is not yet recorded.",
            "",
        ]
    )
    return "\n".join(lines)


def render_review_sheet(
    results: list[CaseResult],
    *,
    sample_size: int,
    dataset_name: str,
    split: str,
) -> str:
    answered = [result for result in results if not result.answer_error]
    if not answered:
        return "# Answer Quality Human Review\n\nNo answered cases.\n"
    if len(answered) <= sample_size:
        sample = answered
    else:
        step = len(answered) / sample_size
        sample = [answered[int(index * step)] for index in range(sample_size)]
    lines = [
        "# Answer Quality Human Review",
        "",
        f"- Dataset: {dataset_name} / {split}",
        f"- Sample: {len(sample)} / {len(answered)} answered cases",
        "- Instructions: read the question, answer and cited evidence, then mark pass/fail. "
        "Record any unsupported claim that the judge missed.",
        "",
    ]
    for index, result in enumerate(sample, start=1):
        judge = result.judge
        auto = (
            f"F{judge.faithfulness}/R{judge.relevance}/C{judge.completeness} "
            f"{'pass' if judge.passed else 'fail'} — {judge.reason}"
            if judge
            else "judge unavailable"
        )
        answer = result.answer.strip().replace("\n", " ")
        evidence = "\n".join(
            f"- [{item.source_id}] {item.document_title} · {item.heading_path} · "
            f"第{item.page}页\n  {item.text.strip().replace(chr(10), ' ')}"
            for item in result.cited_evidence
        )
        lines.extend(
            [
                f"## {index}. `{result.case_id}`",
                "",
                f"**问题**：{result.query}",
                "",
                f"**回答**：{answer}",
                "",
                f"**引用来源**：{result.cited_source_ids or 'none'}",
                "",
                f"**引用证据**：\n{evidence or 'none'}",
                "",
                f"**自动判定**：{auto}",
                "",
                "**人工结论**：☐ 通过　☐ 不通过　　**备注**：",
                "",
                "---",
                "",
            ]
        )
    return "\n".join(lines)


async def run_evaluation(
    *,
    dataset_name: str,
    split: str,
    limit: int,
    concurrency: int,
    top_k: int,
    judge_enabled: bool,
    output: Path | None,
    review_size: int,
) -> int:
    settings = get_settings()
    if settings.store_backend != "postgres":
        raise SystemExit("Answer quality evaluation requires STORE_BACKEND=postgres")
    dataset = get_evaluation_dataset(dataset_name, split)
    cases = list(dataset.cases)
    if limit:
        cases = cases[:limit]
    provider = get_llm_provider()
    store = await PostgresStore.create(
        settings.database_url,
        seed_demo_data=False,
        seed_official_data=False,
    )
    semaphore = asyncio.Semaphore(max(1, concurrency))
    try:
        results = await asyncio.gather(
            *[
                evaluate_case(
                    store,
                    case,
                    provider,
                    top_k=top_k,
                    judge_enabled=judge_enabled,
                    semaphore=semaphore,
                )
                for case in cases
            ]
        )
    finally:
        await store.close()
    result_list = list(results)
    summary = summarize(result_list)
    generated_at = datetime.now(UTC)
    if output is None:
        stamp = generated_at.strftime("%Y%m%d-%H%M%S")
        output = Path("docs/experiments") / f"{stamp}-answer-quality.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    embedding_model = get_embedding_provider().name
    reranker_model = get_reranker_provider().name
    report = render_report(
        result_list,
        summary,
        generated_at=generated_at,
        dataset_name=dataset.name,
        split=dataset.split,
        answer_model=provider.name,
        judge_model=provider.name if judge_enabled else None,
        judge_enabled=judge_enabled,
        embedding_model=embedding_model,
        reranker_model=reranker_model,
        top_k=top_k,
        review_size=review_size,
    )
    output.write_text(report, encoding="utf-8")
    json_path = output.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "dataset": dataset.name,
                "split": dataset.split,
                "embedding_model": embedding_model,
                "reranker_model": reranker_model,
                "answer_model": provider.name,
                "judge_model": provider.name if judge_enabled else None,
                "judge_enabled": judge_enabled,
                "top_k": top_k,
                "review_size": review_size,
                "summary": summary,
                "results": [asdict(result) for result in result_list],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    review_path = output.with_name(f"{output.stem}-review.md")
    review_path.write_text(
        render_review_sheet(
            result_list,
            sample_size=review_size,
            dataset_name=dataset.name,
            split=dataset.split,
        ),
        encoding="utf-8",
    )
    print(report)
    print(f"\nJSON: {json_path}")
    print(f"Human review sheet: {review_path}")
    return 0 if summary["answered"] else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate answer faithfulness and citations")
    parser.add_argument("--dataset", default="policy-synthetic-v1")
    parser.add_argument("--split", default="test", choices=["dev", "test", "all"])
    parser.add_argument("--limit", type=int, default=0, help="Evaluate only the first N cases")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="Only compute deterministic metrics",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--review-size", type=int, default=20)
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            run_evaluation(
                dataset_name=args.dataset,
                split=args.split,
                limit=args.limit,
                concurrency=args.concurrency,
                top_k=args.top_k,
                judge_enabled=not args.skip_judge,
                output=args.output,
                review_size=args.review_size,
            )
        )
    )


if __name__ == "__main__":
    main()
