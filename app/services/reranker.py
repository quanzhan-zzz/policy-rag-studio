import json
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from app.config import get_settings
from app.services.llm import LLMProvider, LLMRateLimitError
from app.services.text import tokenize


class RerankerError(RuntimeError):
    """Raised when a reranker cannot produce a valid ranking."""


@dataclass(frozen=True, slots=True)
class RerankCandidate:
    index: int
    text: str
    heading_path: str
    retrieval_score: float
    dense_score: float
    bm25_score: float


@dataclass(frozen=True, slots=True)
class RerankResult:
    index: int
    score: float


class RerankerProvider(Protocol):
    name: str

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int,
    ) -> list[RerankResult]: ...


class NoneReranker:
    name = "none · fused order"

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int,
    ) -> list[RerankResult]:
        del query
        return [
            RerankResult(index=candidate.index, score=candidate.retrieval_score)
            for candidate in candidates[:top_k]
        ]


class HeuristicReranker:
    name = "heuristic · lexical + rank blend"

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int,
    ) -> list[RerankResult]:
        query_tokens = set(tokenize(query))
        query_lower = query.lower()
        max_bm25 = max((candidate.bm25_score for candidate in candidates), default=1.0) or 1.0
        max_dense = max((candidate.dense_score for candidate in candidates), default=1.0) or 1.0
        ranked: list[RerankResult] = []
        for candidate in candidates:
            coverage = (
                sum(1 for token in query_tokens if token in candidate.text.lower())
                / max(1, len(query_tokens))
            )
            phrase_bonus = 0.25 if query_lower in candidate.text.lower() else 0.0
            heading_bonus = (
                0.12
                if any(token in candidate.heading_path.lower() for token in query_tokens)
                else 0.0
            )
            score = (
                0.45 * candidate.bm25_score / max_bm25
                + 0.25 * candidate.dense_score / max_dense
                + 0.18 * coverage
                + phrase_bonus
                + heading_bonus
            )
            ranked.append(RerankResult(index=candidate.index, score=score))
        ranked.sort(key=lambda result: result.score, reverse=True)
        return ranked[:top_k]


class LLMReranker:
    def __init__(self, provider: LLMProvider, *, max_candidate_chars: int = 220) -> None:
        self.provider = provider
        self.max_candidate_chars = max_candidate_chars
        self.name = f"llm · {provider.name}"

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int,
    ) -> list[RerankResult]:
        if not candidates:
            return []
        payload = [
            {
                "index": position,
                "heading": candidate.heading_path,
                "text": candidate.text[: self.max_candidate_chars],
            }
            for position, candidate in enumerate(candidates, start=1)
        ]
        messages = [
            {
                "role": "system",
                "content": (
                    "你是政策检索重排器。根据用户问题评估候选政策片段的相关性。"
                    "只返回 JSON 数组，不要解释。数组元素格式为 "
                    '{"index": 候选编号, "score": 0到1的小数}。'
                    "按相关性从高到低返回所有候选，编号必须来自输入。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"query": query, "candidates": payload},
                    ensure_ascii=False,
                ),
            },
        ]
        content = self._chat_with_retry(messages)
        parsed = self._parse(content)
        index_map = {
            position: candidate.index
            for position, candidate in enumerate(candidates, start=1)
        }
        position_map = {value: key for key, value in index_map.items()}
        ranked: list[RerankResult] = []
        seen: set[int] = set()
        for item in parsed:
            position = item.get("index")
            score = item.get("score")
            if not isinstance(position, int) or position not in index_map or position in seen:
                continue
            seen.add(position)
            numeric = float(score) if isinstance(score, (int, float)) else 0.0
            ranked.append(
                RerankResult(
                    index=index_map[position],
                    score=max(0.0, min(1.0, numeric)),
                )
            )
        if not ranked:
            raise RerankerError("Reranker 未返回有效候选编号")
        for candidate in candidates:
            position = position_map.get(candidate.index)
            if position is None or position in seen:
                continue
            ranked.append(RerankResult(index=candidate.index, score=-1.0))
        ranked.sort(key=lambda result: result.score, reverse=True)
        return ranked[:top_k]

    def _chat_with_retry(self, messages: list[dict[str, str]]) -> str:
        retry_delays = [5.0, 15.0, 30.0, 60.0]
        for attempt in range(len(retry_delays) + 1):
            try:
                return self.provider.chat(messages, temperature=0.0, max_tokens=1_500)
            except LLMRateLimitError as error:
                if attempt == len(retry_delays):
                    raise
                delay = max(error.retry_after_seconds, retry_delays[attempt])
                time.sleep(delay)
        raise RerankerError("Reranker 请求未完成")

    @staticmethod
    def _parse(content: str) -> list[dict[str, object]]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        start = cleaned.find("[")
        end = cleaned.rfind("]")
        if start < 0 or end < start:
            raise RerankerError("Reranker 返回内容不是 JSON 数组")
        try:
            payload = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as error:
            raise RerankerError("Reranker 返回 JSON 无法解析") from error
        if not isinstance(payload, list):
            raise RerankerError("Reranker 返回格式必须是数组")
        return [item for item in payload if isinstance(item, dict)]


class BGEReranker:
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self.model_name = model_name
        self.name = f"BGE reranker · {model_name}"
        self._model = None

    def warmup(self) -> None:
        self._load_model()

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as error:
                raise RerankerError(
                    "BGE Reranker 需要 sentence-transformers；执行 `uv sync --extra local`"
                ) from error
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(
        self,
        query: str,
        candidates: Sequence[RerankCandidate],
        *,
        top_k: int,
    ) -> list[RerankResult]:
        if not candidates:
            return []
        model = self._load_model()
        scores = model.predict([(query, candidate.text) for candidate in candidates])
        ranked = [
            RerankResult(index=candidate.index, score=float(score))
            for candidate, score in zip(candidates, scores, strict=True)
        ]
        ranked.sort(key=lambda result: result.score, reverse=True)
        return ranked[:top_k]


@lru_cache
def get_reranker_provider() -> RerankerProvider:
    settings = get_settings()
    if settings.reranker_provider == "none":
        return NoneReranker()
    if settings.reranker_provider == "llm":
        from app.services.llm import OpenAICompatibleChatProvider

        llm = OpenAICompatibleChatProvider(
            api_base=settings.reranker_api_base or settings.llm_api_base,
            api_key=settings.reranker_api_key or settings.llm_api_key or "",
            model=settings.reranker_model or settings.llm_model,
            timeout_seconds=settings.reranker_timeout_seconds,
        )
        return LLMReranker(llm)
    if settings.reranker_provider == "bge":
        return BGEReranker(settings.reranker_model or settings.bge_reranker_model)
    return HeuristicReranker()
