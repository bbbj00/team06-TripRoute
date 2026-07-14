# app/graph/workflow.py

import uuid
from typing import Any, Dict

from langfuse import observe
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.state import TripRouteState
from app.graph.checkpointer import get_checkpointer
from app.graph.edges import LINEAR_EDGES
from app.graph.nodes import (
    FINALIZE_NODE,
    FINANCIAL_NODE,
    PARSE_NODE,
    ROUTE_PLANNER_NODE,
    finalize_node,
    financial_node,
    parse_node,
    route_planner_node,
)


def build_trip_route_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """
    TripRoute Agentic Workflow를 LangGraph StateGraph로 조립한다.

    parse_trip_request -> route_planner -> financial -> finalize 순서의
    선형 그래프이며, react_trace는 각 노드가 실제로 실행되며 남기는 기록이다
    (기존처럼 미리 하드코딩된 6단계 설명이 아니라 실제 그래프 실행 결과).

    checkpointer를 넘기면 매 노드 실행 직후 State 스냅샷이 자동 저장돼서(thread_id
    기준), 같은 thread_id로 이어서 실행하거나 중간에 죽어도 재개할 수 있다. None이면
    (SUPABASE_DB_URL 미설정 등) 체크포인트 없이 기존과 동일하게 매번 처음부터 실행된다.
    """
    graph: StateGraph = StateGraph(TripRouteState)

    graph.add_node(PARSE_NODE, parse_node)
    graph.add_node(ROUTE_PLANNER_NODE, route_planner_node)
    graph.add_node(FINANCIAL_NODE, financial_node)
    graph.add_node(FINALIZE_NODE, finalize_node)

    graph.add_edge(START, PARSE_NODE)
    for start, end in LINEAR_EDGES:
        graph.add_edge(start, end)
    graph.add_edge(FINALIZE_NODE, END)

    return graph.compile(checkpointer=checkpointer)


_TRIP_ROUTE_GRAPH = build_trip_route_graph(get_checkpointer())


@observe(name="trip_plan_workflow")
def run_trip_route_workflow(
    user_input: str,
    transport_mode: str = "대중교통",
    people_count: int = 2,
    previous_condition_summary: Dict[str, Any] | None = None,
    previous_result: Dict[str, Any] | None = None,
    thread_id: str | None = None,
) -> Dict[str, Any]:
    """
    컴파일된 TripRoute 그래프를 실행하고 최종 응답 dict를 반환한다.

    previous_condition_summary(직전 턴의 condition_summary)를 넘기면 후속 대화
    맥락을 이어받아 파싱한다(parse_node -> parse_trip_request로 전달됨).
    previous_result(직전 턴의 전체 결과)를 함께 넘기면, 기간 연장 후속 요청에서
    route_planner_node가 기존 일정을 유지한 채 늘어난 날짜만 새로 채운다.

    thread_id(보통 대화 세션 id)는 체크포인터가 State 스냅샷을 구분해서 저장하는 단위다.
    체크포인터가 켜져 있는데(SUPABASE_DB_URL 설정됨) thread_id를 안 넘기면, 이번 호출
    한 번만을 위한 임의 thread_id를 만들어서 쓴다(LangGraph는 체크포인터가 있으면
    thread_id를 요구하므로) — 다음 턴과 이어지진 않지만 실행 자체는 문제없이 된다.

    @observe()로 이 함수 전체를 감싸서, 안쪽 4개 노드(parse/route_planner/financial/
    finalize)의 @observe() 스팬과 Solar/임베딩 호출(langfuse.openai)이 전부 "요청 하나 =
    트레이스 하나"로 같이 묶이게 한다 — 이게 없으면 각 LLM 호출이 서로 무관한 독립
    트레이스로 따로따로 찍혀서 한 사용자 요청 안에서 어디가 느린지 못 본다.
    """
    config = None
    if get_checkpointer() is not None:
        config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}

    final_state = _TRIP_ROUTE_GRAPH.invoke(
        {
            "user_input": user_input,
            "transport_mode": transport_mode,
            "people_count": people_count,
            "previous_condition_summary": previous_condition_summary,
            "previous_result": previous_result,
            "warnings": [],
            "react_trace": [],
        },
        config=config,
    )

    return final_state["result"]
