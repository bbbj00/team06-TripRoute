# app/agents/coordinator.py

from typing import Any, Dict

from app.graph.workflow import run_trip_route_workflow


def run_triproute_coordinator(
    user_input: str,
    transport_mode: str = "대중교통",
    people_count: int = 2,
) -> Dict[str, Any]:
    """
    TripRoute 전체 Workflow를 제어하는 Coordinator.

    실제 단계 조립은 LangGraph 기반 app.graph.workflow에서 수행한다:
    parse_trip_request -> route_planner -> financial -> finalize.
    """

    return run_trip_route_workflow(
        user_input=user_input,
        transport_mode=transport_mode,
        people_count=people_count,
    )
