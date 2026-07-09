from typing import Any, Dict, List

from app.tools.mock_tools import run_tool


def parse_user_input_mock(user_input: str) -> Dict[str, Any]:
    """
    Day 1~2용 Mock 자연어 파싱 함수입니다.
    실제 구현에서는 Coordinator Agent + LLM 구조화 추출로 대체합니다.
    """

    return {
        "city": "강릉",
        "season": "여름",
        "duration": "1박 2일",
        "travel_style": ["바다", "감성 카페", "먹거리"],
        "schedule_intensity": "여유로운 일정",
        "user_input": user_input,
    }


def build_daily_schedule(places: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Mock 일정표 생성 함수입니다.
    """

    return [
        {
            "day": "Day 1",
            "time": "오전",
            "place": "안목해변",
            "reason": "강릉 바다 분위기를 느낄 수 있는 대표 장소입니다.",
            "route_note": "여행 시작점으로 적합합니다.",
        },
        {
            "day": "Day 1",
            "time": "점심",
            "place": "강릉 중앙시장",
            "reason": "먹거리 여행 취향을 반영한 장소입니다.",
            "route_note": "시내권 식사 코스로 배치했습니다.",
        },
        {
            "day": "Day 1",
            "time": "오후",
            "place": "안목 커피거리",
            "reason": "감성 카페 선호를 반영했습니다.",
            "route_note": "안목해변과 함께 방문하기 좋습니다.",
        },
        {
            "day": "Day 2",
            "time": "오전",
            "place": "오죽헌",
            "reason": "강릉의 대표 역사문화 관광지입니다.",
            "route_note": "전날 바다 중심 일정과 균형을 맞춥니다.",
        },
    ]


def run_triproute_react_loop(
    user_input: str,
    transport_mode: str,
    people_count: int,
) -> Dict[str, Any]:
    """
    TripRoute의 최소 ReAct Loop입니다.

    Thought → Action → Observation → Final 흐름을 Mock Tool 기반으로 증명합니다.
    """

    trace = []

    # Thought 1: 사용자 입력을 분석한다.
    parsed = parse_user_input_mock(user_input)
    trace.append(
        {
            "thought": "사용자의 자연어 입력에서 여행 조건을 추출한다.",
            "action": "parse_user_input_mock",
            "observation": parsed,
        }
    )

    # Action 1: 관광지 후보 검색
    search_result = run_tool(
        "search_places",
        {
            "city": parsed["city"],
            "travel_style": parsed["travel_style"],
        },
    )
    places = search_result.observation["places"]
    trace.append(
        {
            "thought": "여행 도시와 취향에 맞는 관광지 후보를 찾는다.",
            "action": "search_places",
            "observation": search_result.observation,
        }
    )

    # Action 2: 연관 관광지 조회
    related_result = run_tool(
        "get_related_places",
        {
            "places": places,
        },
    )
    trace.append(
        {
            "thought": "함께 방문하기 좋은 연관 관광지를 찾는다.",
            "action": "get_related_places",
            "observation": related_result.observation,
        }
    )

    # Action 3: 이동 정보 조회
    route_result = run_tool(
        "get_route_info",
        {
            "places": places,
            "transport_mode": transport_mode,
        },
    )
    route_segments = route_result.observation["route_segments"]
    trace.append(
        {
            "thought": "장소 간 이동시간과 동선 정보를 계산한다.",
            "action": "get_route_info",
            "observation": route_result.observation,
        }
    )

    # Action 4: 비용 계산
    cost_result = run_tool(
        "estimate_cost",
        {
            "route_segments": route_segments,
            "people_count": people_count,
            "transport_mode": transport_mode,
        },
    )
    cost_summary = cost_result.observation["cost_summary"]
    trace.append(
        {
            "thought": "이동수단과 인원수를 바탕으로 예상 비용을 계산한다.",
            "action": "estimate_cost",
            "observation": cost_result.observation,
        }
    )

    # Final: 최종 응답 조립
    final_answer = {
        "condition_summary": {
            "user_input": user_input,
            "city": parsed["city"],
            "season": parsed["season"],
            "duration": parsed["duration"],
            "travel_style": parsed["travel_style"],
            "transport_mode": transport_mode,
            "people_count": people_count,
            "schedule_intensity": parsed["schedule_intensity"],
        },
        "daily_schedule": build_daily_schedule(places),
        "route_summary": route_segments,
        "cost_summary": cost_summary,
        "warnings": [
            "현재 결과는 Mock Tool 기반 MVP 응답입니다.",
            "대중교통 시간과 비용은 참고용 추정치입니다.",
        ],
        "react_trace": trace,
    }

    return final_answer