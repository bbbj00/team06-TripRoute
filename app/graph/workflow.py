# app/graph/workflow.py

from typing import Any, Dict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.core.state import TripRouteState
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


def build_trip_route_graph() -> CompiledStateGraph:
    """
    TripRoute Agentic Workflow를 LangGraph StateGraph로 조립한다.

    parse_trip_request -> route_planner -> financial -> finalize 순서의
    선형 그래프이며, react_trace는 각 노드가 실제로 실행되며 남기는 기록이다
    (기존처럼 미리 하드코딩된 6단계 설명이 아니라 실제 그래프 실행 결과).
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

    return graph.compile()


_TRIP_ROUTE_GRAPH = build_trip_route_graph()


def run_trip_route_workflow(
    user_input: str,
    transport_mode: str = "대중교통",
    people_count: int = 2,
    previous_condition_summary: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    컴파일된 TripRoute 그래프를 실행하고 최종 응답 dict를 반환한다.

    previous_condition_summary(직전 턴의 condition_summary)를 넘기면 후속 대화
    맥락을 이어받아 파싱한다(parse_node -> parse_trip_request로 전달됨).
    """
    final_state = _TRIP_ROUTE_GRAPH.invoke(
        {
            "user_input": user_input,
            "transport_mode": transport_mode,
            "people_count": people_count,
            "previous_condition_summary": previous_condition_summary,
            "warnings": [],
            "react_trace": [],
        }
    )

    return final_state["result"]
