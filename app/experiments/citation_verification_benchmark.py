import argparse
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from app.schemas import AnswerCitation
from app.services.adversarial_eval import load_adversarial_cases, score_adversarial_answer
from app.services.citation_verification import (
    VERIFICATION_FAILED_ANSWER,
    CitationVerifier,
    LLMCitationVerifier,
    RuleCitationVerifier,
    VerificationResult,
    get_citation_verifier_llm_provider,
)


@dataclass(slots=True)
class OfficialVerificationMetrics:
    case_count: int
    answered: int
    abstentions: int
    removed_claims: int
    removed_citations: int
    citation_precision: float
    citation_recall: float
    invalid_citation_cases: int
    verification_p50_ms: float
    verification_p95_ms: float


@dataclass(slots=True)
class AdversarialVerificationMetrics:
    case_count: int
    passed: int
    false_answers: int
    correct_abstentions: int
    expected_abstention_cases: int
    prompt_injection_leaks: int
    removed_claims: int
    removed_citations: int
    verification_p50_ms: float
    verification_p95_ms: float


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sorted(values)[max(0, math.ceil(len(values) * 0.95) - 1)], 3)


def _p50(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sorted(values)[max(0, math.ceil(len(values) * 0.5) - 1)], 3)


def _citations_from_evidence(result: dict) -> list[AnswerCitation]:
    return [
        AnswerCitation(
            source_id=int(item["source_id"]),
            chunk_id=str(item.get("chunk_id", f"source-{item['source_id']}")),
            document_id=str(item["document_id"]),
            document_title=str(item["document_title"]),
            heading_path=str(item["heading_path"]),
            page=int(item["page"]),
            text=str(item["text"]),
        )
        for item in result.get("cited_evidence", [])
    ]


def _verify_safely(
    verifier: CitationVerifier,
    query: str,
    answer: str,
    citations: list[AnswerCitation],
) -> VerificationResult:
    try:
        return verifier.verify(query, answer, citations)
    except Exception as error:  # noqa: BLE001 - keep the benchmark complete
        return VerificationResult(
            answer=VERIFICATION_FAILED_ANSWER,
            verifier=verifier.name,
            status="verification_failed",
            claims=(),
            supported_claim_count=0,
            removed_claim_count=0,
            removed_citation_count=0,
            latency_ms=0.0,
            fallback_reason=f"{type(error).__name__}: {error}",
        )


def _score_official_citation(
    result: dict,
    verified_answer: str,
    citations: list[AnswerCitation],
) -> tuple[float, float, int]:
    citation_map = {citation.source_id: citation for citation in citations}
    referenced_ids = sorted({int(value) for value in re.findall(r"\[(\d+)\]", verified_answer)})
    valid_ids = [source_id for source_id in referenced_ids if source_id in citation_map]
    invalid = [source_id for source_id in referenced_ids if source_id not in citation_map]
    expected_document_id = result.get("expected_document_id", "")
    expected_heading = str(result.get("expected_heading", "")).lower()
    matched = sum(
        citation_map[source_id].document_id == expected_document_id
        and expected_heading in citation_map[source_id].heading_path.lower()
        for source_id in valid_ids
    )
    precision = matched / len(valid_ids) if valid_ids else 0.0
    recall = 1.0 if matched else 0.0
    return round(precision, 4), recall, len(invalid)


def evaluate_official(path: Path, verifier: CitationVerifier):
    payload = json.loads(path.read_text(encoding="utf-8"))
    precision_values: list[float] = []
    recall_values: list[float] = []
    verification_times: list[float] = []
    abstentions = 0
    removed_claims = 0
    removed_citations = 0
    invalid_cases = 0
    details: list[dict] = []
    for result in payload["results"]:
        if result.get("answer_error"):
            continue
        citations = _citations_from_evidence(result)
        verification = _verify_safely(
            verifier,
            result["query"],
            result["answer"],
            citations,
        )
        precision, recall, invalid = _score_official_citation(
            result,
            verification.answer,
            citations,
        )
        precision_values.append(precision)
        recall_values.append(recall)
        verification_times.append(verification.latency_ms)
        abstentions += verification.status == "abstained"
        removed_claims += verification.removed_claim_count
        removed_citations += verification.removed_citation_count
        invalid_cases += int(invalid > 0)
        details.append(
            {
                "case_id": result["case_id"],
                "status": verification.status,
                "removed_claims": verification.removed_claim_count,
                "removed_citations": verification.removed_citation_count,
                "citation_precision": precision,
                "citation_recall": recall,
                "verified_answer": verification.answer,
                "claims": [asdict(claim) for claim in verification.claims],
            }
        )
    count = max(1, len(precision_values))
    metrics = OfficialVerificationMetrics(
        case_count=len(payload["results"]),
        answered=len(precision_values),
        abstentions=abstentions,
        removed_claims=removed_claims,
        removed_citations=removed_citations,
        citation_precision=round(sum(precision_values) / count, 4),
        citation_recall=round(sum(recall_values) / count, 4),
        invalid_citation_cases=invalid_cases,
        verification_p50_ms=_p50(verification_times),
        verification_p95_ms=_p95(verification_times),
    )
    return metrics, details


def evaluate_adversarial(path: Path, verifier: CitationVerifier):
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = {case.id: case for case in load_adversarial_cases()}
    verification_times: list[float] = []
    removed_claims = 0
    removed_citations = 0
    passed = 0
    false_answers = 0
    correct_abstentions = 0
    expected_abstentions = 0
    leaks = 0
    details: list[dict] = []
    for result in payload["results"]:
        case = cases[result["id"]]
        citations = [AnswerCitation.model_validate(item) for item in result["citations"]]
        verification = _verify_safely(
            verifier,
            case.query,
            result["answer"],
            citations,
        )
        outcome = score_adversarial_answer(
            case,
            verification.answer,
            invalid_citation_ids=result.get("invalid_citation_ids", []),
        )
        passed += outcome.passed
        false_answers += outcome.false_answer
        if case.expected_behavior == "abstain":
            expected_abstentions += 1
            correct_abstentions += outcome.passed
        leaks += outcome.leak_detected

        removed_claims += verification.removed_claim_count
        removed_citations += verification.removed_citation_count
        verification_times.append(verification.latency_ms)
        details.append(
            {
                "case_id": case.id,
                "status": verification.status,
                "removed_claims": verification.removed_claim_count,
                "removed_citations": verification.removed_citation_count,
                "passed": outcome.passed,
                "false_answer": outcome.false_answer,
                "forbidden_hits": outcome.forbidden_hits,
                "verified_answer": verification.answer,
            }
        )
    metrics = AdversarialVerificationMetrics(
        case_count=len(payload["results"]),
        passed=passed,
        false_answers=false_answers,
        correct_abstentions=correct_abstentions,
        expected_abstention_cases=expected_abstentions,
        prompt_injection_leaks=leaks,
        removed_claims=removed_claims,
        removed_citations=removed_citations,
        verification_p50_ms=_p50(verification_times),
        verification_p95_ms=_p95(verification_times),
    )
    return metrics, details


def main() -> None:
    parser = argparse.ArgumentParser(description="Rescore real answers with citation verifier")
    parser.add_argument("--verifier", choices=["rule", "llm"], default="rule")
    parser.add_argument(
        "--official-json",
        type=Path,
        default=Path("docs/experiments/20261124-official-answer-quality-test.json"),
    )
    parser.add_argument(
        "--adversarial-json",
        type=Path,
        default=Path("docs/experiments/20261124-adversarial-evaluation.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/experiments/20261124-citation-verification-rule.md"),
    )
    args = parser.parse_args()
    official_payload = json.loads(args.official_json.read_text(encoding="utf-8"))
    adversarial_payload = json.loads(args.adversarial_json.read_text(encoding="utf-8"))
    verifier = (
        LLMCitationVerifier(get_citation_verifier_llm_provider())
        if args.verifier == "llm"
        else RuleCitationVerifier()
    )
    official, official_details = evaluate_official(args.official_json, verifier)
    adversarial, adversarial_details = evaluate_adversarial(
        args.adversarial_json,
        verifier,
    )
    generated_at = datetime.now(UTC)
    abstention_ratio = (
        f"{adversarial.correct_abstentions} / {adversarial.expected_abstention_cases}"
    )
    report = f"""# Citation Verification Evaluation

- Generated: {generated_at.isoformat()}
- Verifier: `{verifier.name}`
- Inputs are previously generated real-model answers; only verifier post-processing is replayed.
- Answer source: {official_payload.get("answer_model", "unknown")}
- Adversarial source generated: {adversarial_payload.get("generated_at", "unknown")}

## Official answer-quality set

| Metric | Result |
| --- | ---: |
| Cases | {official.case_count} |
| Answered | {official.answered} |
| Abstentions after verification | {official.abstentions} |
| Removed claims | {official.removed_claims} |
| Removed citations | {official.removed_citations} |
| Citation precision | {official.citation_precision:.4f} |
| Citation recall | {official.citation_recall:.4f} |
| Invalid citation cases | {official.invalid_citation_cases} |
| Verification P50 | {official.verification_p50_ms:.3f} ms |
| Verification P95 | {official.verification_p95_ms:.3f} ms |

## Adversarial set

| Metric | Result |
| --- | ---: |
| Cases | {adversarial.case_count} |
| Correct behavior | {adversarial.passed} |
| False answers | {adversarial.false_answers} |
| Correct abstentions | {abstention_ratio} |
| Prompt-injection leaks | {adversarial.prompt_injection_leaks} |
| Removed claims | {adversarial.removed_claims} |
| Removed citations | {adversarial.removed_citations} |
| Verification P50 | {adversarial.verification_p50_ms:.3f} ms |
| Verification P95 | {adversarial.verification_p95_ms:.3f} ms |

## Decision gate

- The verifier is acceptable only if citation precision and false-answer behavior improve
  without material citation-recall loss.
- Previous real-model baseline: citation precision 0.668, citation recall 1.0.
- Previous adversarial baseline: 23/25 correct, 1/4 prompt-injection leaks.

## Case changes

### Official

| Case | Status | Removed | Cite P | Cite R |
| --- | --- | ---: | ---: | ---: |
"""
    for detail in official_details:
        report += (
            f"| `{detail['case_id']}` | {detail['status']} | "
            f"{detail['removed_claims']} | {detail['citation_precision']:.2f} | "
            f"{detail['citation_recall']:.0f} |\n"
        )
    report += """
### Adversarial

| Case | Status | Removed | Pass |
| --- | --- | ---: | :---: |
"""
    for detail in adversarial_details:
        report += (
            f"| `{detail['case_id']}` | {detail['status']} | "
            f"{detail['removed_claims']} | {'✓' if detail['passed'] else '✗'} |\n"
        )
    report += """
## Limitations

- Rule verification measures lexical/numeric overlap, not full semantic entailment.
- Previously generated answers are reused; this is not a fresh model generation run.
- Fresh real-model generation results are reported separately; this replay isolates verifier
  behavior on identical prior answers.
- Rule verification is not sufficient for default enablement because answer completeness can
  fall and similar-matter questions can still produce unsafe answers.
"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    args.output.with_suffix(".json").write_text(
        json.dumps(
            {
                "generated_at": generated_at.isoformat(),
                "verifier": verifier.name,
                "official": asdict(official),
                "adversarial": asdict(adversarial),
                "official_details": official_details,
                "adversarial_details": adversarial_details,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report)


if __name__ == "__main__":
    main()
