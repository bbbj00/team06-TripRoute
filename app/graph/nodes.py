# app/graph/nodes.py

from typing import Any, Dict

from app.agents.financial import build_financial_summary
from app.agents.route_planner import build_route_plan
from app.core.state import TripRouteState
from app.services.solar import parse_trip_request

PARSE_NODE = "parse_trip_request"
ROUTE_PLANNER_NODE = "route_planner"
FINANCIAL_NODE = "financial"
FINALIZE_NODE = "finalize"


def _trace_entry(step: int, action: str, description: str, **extra: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {"step": step, "action": action, "description": description}
    entry.update(extra)
    return entry


def parse_node(state: TripRouteState) -> Dict[str, Any]:
    """1단계: Solar API(또는 Mock parser)로 사용자 입력을 여행 조건으로 구조화한다."""
    parsed, parse_warnings = parse_trip_request(
        state["user_input"],
        state.get("previous_condition_summary"),
    )
    parser = parsed.get("_parser", "unknown")

    return {
        "city": parsed.get("city"),
        "season": parsed.get("season"),
        "duration": parsed.get("duration"),
        "travel_style": parsed.get("travel_style", []),
        "must_include_places": parsed.get("must_include_places", []),
        "schedule_intensity": parsed.get("schedule_intensity"),
        "prefer_local": parsed.get("prefer_local", False),
        "prefer_budget": parsed.get("prefer_budget", False),
        "is_peak_season": parsed.get("is_peak_season", False),
        "parser": parser,
        "warnings": list(parse_warnings),
        "react_trace": [
            _trace_entry(
                1,
                "parse_trip_request",
                "Solar API 또는 Mock parser로 사용자 입력을 여행 조건으로 구조화",
                parser=parser,
            )
        ],
    }


def route_planner_node(state: TripRouteState) -> Dict[str, Any]:
    """2단계: Route Planner Agent가 관광지 후보/연관 장소/동선/일정을 만든다."""
    parsed = {
        "city": state.get("city"),
        "season": state.get("season"),
        "duration": state.get("duration"),
        "travel_style": state.get("travel_style", []),
        "must_include_places": state.get("must_include_places", []),
        "schedule_intensity": state.get("schedule_intensity"),
        "prefer_local": state.get("prefer_local", False),
        "prefer_budget": state.get("prefer_budget", False),
        "is_peak_season": state.get("is_peak_season", False),
    }

    route_plan = build_route_plan(
        parsed=parsed,
        transport_mode=state["transport_mode"],
        people_count=state["people_count"],
    )

    return {
        "candidate_places": route_plan.get("candidate_places", []),
        "rag_ranked_places": route_plan.get("rag_ranked_places", []),
        "related_places": route_plan.get("related_places", []),
        "selected_places": route_plan.get("selected_places", []),
        "route_summary": route_plan.get("route_summary", []),
        "daily_schedule": route_plan.get("daily_schedule", []),
        "lodging_place": route_plan.get("lodging_place"),
        "data_source": route_plan.get("data_source", "mock"),
        "warnings": list(route_plan.get("warnings", [])),
        "react_trace": [
            _trace_entry(
                2,
                "build_route_plan",
                "관광지 후보 검색부터 연관 장소·이동 동선·일정 배정까지 "
                "Route Planner Agent가 처리",
            )
        ],
    }


def financial_node(state: TripRouteState) -> Dict[str, Any]:
    """3단계: Financial Agent가 교통비/식비/입장료/숙박비 등 예상 비용을 계산한다."""
    route_plan = {
        "route_summary": state.get("route_summary", []),
        "daily_schedule": state.get("daily_schedule", []),
        "selected_places": state.get("selected_places", []),
        "lodging_place": state.get("lodging_place"),
        "is_peak_season": state.get("is_peak_season", False),
    }

    cost_summary = build_financial_summary(
        route_plan=route_plan,
        transport_mode=state["transport_mode"],
        people_count=state["people_count"],
    )

    return {
        "cost_summary": cost_summary,
        "react_trace": [
            _trace_entry(
                3,
                "build_financial_summary",
                "교통비·식비·입장료·숙박비 등 예상 비용을 Financial Agent가 계산",
            )
        ],
    }


def finalize_node(state: TripRouteState) -> Dict[str, Any]:
    """4단계: 각 Agent 결과를 최종 응답 형태로 조립한다."""
    warnings = list(state.get("warnings", []))

    if state.get("data_source", "mock") == "mock":
        warnings.append(
            "실제 관광 API 호출 실패 또는 미연결 상태로 "
            "Mock fallback 데이터를 사용했습니다."
        )

    if state.get("transport_mode") == "대중교통":
        warnings.append(
            "대중교통 시간과 비용은 자동차 경로 기반 참고용 추정치입니다."
        )

    finalize_entry = _trace_entry(
        4,
        "finalize_response",
        "Coordinator가 각 Agent 결과를 최종 응답으로 조립",
    )
    # finalize 노드 자신의 트레이스는 이 시점엔 아직 state에 병합되지 않았으므로,
    # 최종 응답에 넣을 react_trace에는 직접 이어붙여야 4단계가 전부 담긴다.
    full_react_trace = list(state.get("react_trace", [])) + [finalize_entry]

    result = {
        "condition_summary": {
            "user_input": state.get("user_input"),
            "city": state.get("city"),
            "season": state.get("season"),
            "duration": state.get("duration"),
            "travel_style": state.get("travel_style", []),
            "must_include_places": state.get("must_include_places", []),
            "schedule_intensity": state.get("schedule_intensity"),
            "prefer_local": state.get("prefer_local", False),
            "prefer_budget": state.get("prefer_budget", False),
            "is_peak_season": state.get("is_peak_season", False),
            "transport_mode": state.get("transport_mode"),
            "people_count": state.get("people_count"),
            "parser": state.get("parser", "unknown"),
            "data_source": state.get("data_source", "mock"),
        },
        "daily_schedule": state.get("daily_schedule", []),
        "route_summary": state.get("route_summary", []),
        "cost_summary": state.get("cost_summary", {}),
        "warnings": warnings,
        "react_trace": full_react_trace,
    }

    return {
        "react_trace": [finalize_entry],
        "result": result,
    }
