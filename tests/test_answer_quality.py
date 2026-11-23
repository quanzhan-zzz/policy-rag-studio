import pytest

from app.experiments.answer_quality import (
    CaseResult,
    EvidenceExcerpt,
    JudgeScore,
    parse_judge_payload,
    render_review_sheet,
    score_citations,
    summarize,
)
from app.schemas import (
    AnswerCitation,
    AnswerResponse,
    RetrievalRun,
    RetrievalStrategy,
)
from app.services.seed import EvaluationCase


def _case() -> EvaluationCase:
    return EvaluationCase(
        id="case-01",
        query="申请材料有哪些？",
        expected_document_id="doc-1",
        expected_heading="三、申请材料",
        failure_type="test",
    )


def _citation(source_id: int, *, document_id: str = "doc-1", heading: str = "三、申请材料"):
    return AnswerCitation(
        source_id=source_id,
        chunk_id=f"chunk-{source_id}",
        document_id=document_id,
        document_title=f"document-{document_id}",
        heading_path=heading,
        page=1,
        text="evidence",
    )


def _response(answer: str, citations: list[AnswerCitation]) -> AnswerResponse:
    return AnswerResponse(
        query="申请材料有哪些？",
        answer=answer,
        model="test-model",
        retrieval=RetrievalRun(
            strategy=RetrievalStrategy.HYBRID_RERANK,
            label="Hybrid + Rerank",
            latency_ms=1.0,
            trace_id="trace-1",
            results=[],
        ),
        citations=citations,
        total_ms=12.5,
        total_tokens=16,
        grounding_status="supported",
    )


def test_parse_judge_payload_tolerates_fence_and_clamps_scores() -> None:
    result = parse_judge_payload(
        """评审结果：
```json
{
  "faithfulness": 7,
  "relevance": 4,
  "completeness": 0,
  "citation_support": "SUPPORTED",
  "unsupported_claims": [],
  "pass": true,
  "reason": "回答与证据一致"
}
```"""
    )

    assert result.faithfulness == 5
    assert result.relevance == 4
    assert result.completeness == 1
    assert result.citation_support == "supported"
    assert result.passed is True


def test_parse_judge_payload_rejects_unsupported_claims_even_if_model_passes() -> None:
    result = parse_judge_payload(
        """
        {
          "faithfulness": 5,
          "relevance": 5,
          "completeness": 4,
          "citation_support": "supported",
          "unsupported_claims": ["多出的办理时限"],
          "pass": true,
          "reason": "存在无证据结论"
        }
        """
    )

    assert result.passed is False
    assert result.unsupported_claims == ["多出的办理时限"]


def test_score_citations_uses_unique_valid_sources_and_tracks_invalid_ids() -> None:
    response = _response(
        "材料包括申请书[1]、身份证明[2]和无关材料[3]，另有无效引用[9]。",
        [_citation(1), _citation(2), _citation(3, heading="四、办理流程")],
    )

    precision, recall, cited_valid, invalid = score_citations(response, _case())

    assert precision == pytest.approx(2 / 3)
    assert recall == 1.0
    assert cited_valid == [1, 2, 3]
    assert invalid == [9]


def test_score_citations_returns_zero_recall_without_gold_citation() -> None:
    response = _response("回答[1]", [_citation(1, heading="四、办理流程")])

    precision, recall, _, _ = score_citations(response, _case())

    assert precision == 0.0
    assert recall == 0.0


def test_summarize_excludes_failed_answers_from_quality_averages() -> None:
    passed = CaseResult(
        case_id="pass",
        query="q1",
        expected_heading="h",
        trace_id="trace-pass",
        reranker_detail="BGE reranker · test",
        retrieval_hit=True,
        gold_rank=1,
        answer="a[1]",
        citation_precision=1.0,
        citation_recall=1.0,
        cited_source_ids=[1],
        cited_evidence=[],
        invalid_citation_ids=[],
        grounding_status="supported",
        answer_ms=10.0,
        total_tokens=10,
        judge=JudgeScore(5, 5, 4, "supported", [], True, "ok"),
        judge_error=None,
        answer_error=None,
    )
    failed = CaseResult(
        case_id="failed",
        query="q2",
        expected_heading="h",
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
        answer_error="LLMProviderError: timeout",
    )

    summary = summarize([passed, failed])

    assert summary["case_count"] == 2
    assert summary["answered"] == 1
    assert summary["answer_errors"] == 1
    assert summary["reranker_fallbacks"] == 0
    assert summary["judge_pass_rate"] == 1.0
    assert summary["avg_faithfulness"] == 5.0


def test_review_sheet_contains_blank_human_decision() -> None:
    result = CaseResult(
        case_id="case-01",
        query="申请材料有哪些？",
        expected_heading="三、申请材料",
        trace_id="trace-1",
        reranker_detail="BGE reranker · test",
        retrieval_hit=True,
        gold_rank=1,
        answer="申请书和身份证明。[1]",
        citation_precision=1.0,
        citation_recall=1.0,
        cited_source_ids=[1],
        cited_evidence=[
            EvidenceExcerpt(
                source_id=1,
                document_id="doc-1",
                document_title="办事指南",
                heading_path="三、申请材料",
                page=1,
                text="提交申请书和身份证明。",
            )
        ],
        invalid_citation_ids=[],
        grounding_status="supported",
        answer_ms=10.0,
        total_tokens=10,
        judge=None,
        judge_error="timeout",
        answer_error=None,
    )

    sheet = render_review_sheet(
        [result],
        sample_size=20,
        dataset_name="policy-synthetic-v1",
        split="test",
    )

    assert "人工结论" in sheet
    assert "judge unavailable" in sheet
    assert "申请书和身份证明。[1]" in sheet
    assert "提交申请书和身份证明。" in sheet
