import time
from collections.abc import Iterator, Sequence

import pytest

from app.schemas import ChunkStrategy, QueryPlanningMode
from app.services.llm import ChatResult, TokenUsage
from app.services.query_planning import QueryPlan, plan_query
from app.services.retrieval import run_planned_retrieval
from app.store import InMemoryStore


class FakePlannerProvider:
    name = "fake planner"

    def __init__(self, content: str, *, delay: float = 0.0) -> None:
        self.content = content
        self.delay = delay

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> str:
        return self.content

    def chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> ChatResult:
        time.sleep(self.delay)
        return ChatResult(
            content=self.content,
            usage=TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ) -> Iterator[str]:
        yield self.content

    def stream_chat_with_usage(
        self,
        messages: Sequence[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 800,
    ):
        yield self.content


@pytest.mark.asyncio
async def test_none_mode_keeps_original_query() -> None:
    plan = await plan_query("原问题", QueryPlanningMode.NONE)

    assert plan.retrieval_queries == ("原问题",)
    assert plan.fallback_reason is None
    assert plan.usage.total_tokens == 0


@pytest.mark.asyncio
async def test_rewrite_mode_parses_plan_and_usage() -> None:
    provider = FakePlannerProvider(
        '{"rewritten_query":"公司变更法定代表人材料","constraints":["公司","法定代表人"],'
        '"subqueries":["法定代表人材料"],"reason":"规范表达"}'
    )

    plan = await plan_query(
        "法人变了要带啥",
        QueryPlanningMode.REWRITE,
        llm_provider=provider,
    )

    assert plan.retrieval_queries == ("法人变了要带啥", "公司变更法定代表人材料")
    assert plan.constraints == ("公司", "法定代表人")
    assert plan.usage.total_tokens == 30
    assert plan.fallback_reason is None


@pytest.mark.asyncio
async def test_decompose_mode_limits_and_deduplicates_queries() -> None:
    provider = FakePlannerProvider(
        '{"rewritten_query":"公司变更登记条件材料时限",'
        '"constraints":["公司变更"],'
        '"subqueries":["公司变更条件","公司变更材料","公司变更时限","公司变更条件","额外查询"],'
        '"reason":"多条件拆解"}'
    )

    plan = await plan_query(
        "公司变更有什么条件和材料，多久办完",
        QueryPlanningMode.DECOMPOSE,
        llm_provider=provider,
        max_subqueries=3,
    )

    assert plan.retrieval_queries == (
        "公司变更有什么条件和材料，多久办完",
        "公司变更登记条件材料时限",
        "公司变更条件",
    )
    assert len(plan.subqueries) == 3


@pytest.mark.asyncio
async def test_planner_timeout_falls_back_to_original_query() -> None:
    provider = FakePlannerProvider('{"rewritten_query":"不会到达"}', delay=0.2)

    plan = await plan_query(
        "原始问题",
        QueryPlanningMode.REWRITE,
        llm_provider=provider,
        timeout_seconds=0.01,
    )

    assert plan.retrieval_queries == ("原始问题",)
    assert plan.fallback_reason == "timeout"


@pytest.mark.asyncio
async def test_invalid_planner_json_falls_back_to_original_query() -> None:
    provider = FakePlannerProvider("not json")

    plan = await plan_query(
        "原始问题",
        QueryPlanningMode.DECOMPOSE,
        llm_provider=provider,
    )

    assert plan.retrieval_queries == ("原始问题",)
    assert plan.fallback_reason is not None


@pytest.mark.asyncio
async def test_planned_retrieval_traces_subqueries_and_fusion() -> None:
    store = InMemoryStore(seed_demo_data=True, seed_official_data=True)
    chunks = await store.all_chunks(ChunkStrategy.HEADING)
    plan = QueryPlan(
        original_query="公司变更法定代表人需要哪些材料，多久办结？",
        mode=QueryPlanningMode.DECOMPOSE,
        provider="test",
        rewritten_query="公司变更登记 法定代表人 材料 时限",
        subqueries=("公司变更法定代表人需要哪些材料", "公司变更登记多久办结"),
        constraints=("公司变更", "法定代表人"),
        retrieval_queries=(
            "公司变更登记 法定代表人 材料 时限",
            "公司变更法定代表人需要哪些材料",
            "公司变更登记多久办结",
        ),
        latency_ms=12.0,
        usage=TokenUsage(total_tokens=30),
    )

    run, trace = await run_planned_retrieval(
        store,
        chunks,
        plan,
        top_k=5,
    )

    assert run.results
    assert run.label.endswith("decompose")
    assert any(stage.key == "query_plan" for stage in trace.stages)
    assert any(stage.key == "multi_query_fusion" for stage in trace.stages)
    assert sum(stage.key.startswith("planned_query_") for stage in trace.stages) == 3
    assert trace.total_ms >= 12.0
