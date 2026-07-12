# app/agents/coordinator.py

from typing import Any, Dict

from app.agents.financial import build_financial_summary
from app.agents.route_planner import build_route_plan
from app.services.solar import parse_trip_request


def run_triproute_coordinator(
    user_input: str,
    transport_mode: str = "대중교통",
    people_count: int = 2,
) -> Dict[str, Any]:
    """
    TripRoute 전체 Workflow를 제어하는 Coordinator.

    1. Solar API 또는 Mock parser로 사용자 입력 파싱
    2. Route Planner로 장소/동선/일정 생성
    3. Financial로 예상 비용 계산
    4. 최종 응답 조립
    """

    warnings: list[str] = []

    # 1. 사용자 입력 파싱
    parsed, parse_warnings = parse_trip_request(user_input)
    warnings.extend(parse_warnings)

    # UI/API에서 받은 값을 우선 반영
    parsed["transport_mode"] = transport_mode
    parsed["people_count"] = people_count

    # 2. Route Planner 실행
    route_plan = build_route_plan(
        parsed=parsed,
        transport_mode=transport_mode,
        people_count=people_count,
    )

    # 3. Financial 실행
    cost_summary = build_financial_summary(
        route_plan=route_plan,
        transport_mode=transport_mode,
        people_count=people_count,
    )

    # 4. Route Planner 경고 반영
    warnings.extend(route_plan.get("warnings", []))

    # 기존 Mock Route Planner는 data_source가 없을 수 있으므로
    # 기본값을 mock으로 설정
    data_source = route_plan.get("data_source", "mock")

    if data_source == "mock":
        warnings.append(
            "실제 관광 API 호출 실패 또는 미연결 상태로 "
            "Mock fallback 데이터를 사용했습니다."
        )

    if transport_mode == "대중교통":
        warnings.append(
            "대중교통 시간과 비용은 자동차 경로 기반 참고용 추정치입니다."
        )

    # 5. 기존 ReAct 테스트 호환용 trace
    react_trace = [
        {
            "step": 1,
            "action": "parse_trip_request",
            "description": (
                "Solar API 또는 Mock parser로 "
                "사용자 입력을 여행 조건으로 구조화"
            ),
            "parser": parsed.get("_parser", "unknown"),
        },
        {
            "step": 2,
            "action": "search_places",
            "description": (
                "사용자 여행 조건을 바탕으로 "
                "주요 관광지 후보를 검색"
            ),
        },
        {
            "step": 3,
            "action": "get_related_places",
            "description": (
                "선택된 관광지와 함께 방문하기 좋은 "
                "연관 장소를 조회"
            ),
        },
        {
            "step": 4,
            "action": "get_route_info",
            "description": (
                "장소 간 이동 시간과 동선 정보를 생성"
            ),
        },
        {
            "step": 5,
            "action": "estimate_cost",
            "description": (
                "교통비와 여행 예상 비용을 계산"
            ),
        },
        {
            "step": 6,
            "action": "build_final_response",
            "description": (
                "Coordinator가 최종 응답을 조립"
            ),
        },
    ]

    # 6. 최종 응답
    return {
        "condition_summary": {
            "user_input": user_input,
            "city": parsed.get("city"),
            "season": parsed.get("season"),
            "duration": parsed.get("duration"),
            "travel_style": parsed.get("travel_style", []),
            "schedule_intensity": parsed.get(
                "schedule_intensity"
            ),
            "prefer_local": parsed.get("prefer_local", False),
            "transport_mode": transport_mode,
            "people_count": people_count,
            "parser": parsed.get("_parser", "unknown"),
            "data_source": data_source,
        },
        "daily_schedule": route_plan.get(
            "daily_schedule",
            [],
        ),
        "route_summary": route_plan.get(
            "route_summary",
            [],
        ),
        "cost_summary": cost_summary,
        "warnings": warnings,
        "react_trace": react_trace,
    }