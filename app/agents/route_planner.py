# app/agents/route_planner.py

from typing import Any, Dict, List

from app.tools.mock_tools import run_tool


def _get_observation(tool_result: Any) -> Any:
    """
    Mock ToolResult에서 observation만 안전하게 꺼낸다.
    dict, 객체 형태를 모두 대응한다.
    """
    if isinstance(tool_result, dict):
        if "observation" in tool_result:
            return tool_result["observation"]
        if "output" in tool_result:
            return tool_result["output"]
        return tool_result

    if hasattr(tool_result, "observation"):
        return tool_result.observation

    if hasattr(tool_result, "output"):
        return tool_result.output

    return tool_result


def _extract_list(tool_result: Any, *keys: str) -> List[Dict[str, Any]]:
    """
    ToolResult observation 안에서 리스트 데이터를 꺼낸다.
    예:
    - {"places": [...]}
    - {"related_places": [...]}
    - {"route_segments": [...]}
    """
    observation = _get_observation(tool_result)

    if isinstance(observation, list):
        return observation

    if isinstance(observation, dict):
        for key in keys:
            value = observation.get(key)
            if isinstance(value, list):
                return value

        # 키 이름이 달라도 첫 번째 list 값을 찾아서 반환
        for value in observation.values():
            if isinstance(value, list):
                return value

    return []


def _get_place_name(place: Dict[str, Any]) -> str:
    return (
        place.get("name")
        or place.get("place_name")
        or place.get("title")
        or place.get("related_place")
        or place.get("base_place")
        or "장소명 없음"
    )


def build_route_plan(
    parsed: Dict[str, Any],
    transport_mode: str,
    people_count: int,
) -> Dict[str, Any]:
    """
    Route Planner 역할:
    - 장소 후보 검색
    - 연관 장소 확장
    - 이동 동선 생성
    - 시간대별 일정표 구성
    """

    city = parsed.get("city", "강릉")
    travel_style = parsed.get("travel_style", [])

    # 1. 관광지 후보 검색
    search_result = run_tool(
        "search_places",
        {
            "city": city,
            "travel_style": travel_style,
        },
    )
    places = _extract_list(search_result, "places", "tourist_spots", "results")

    # 2. 연관 장소 검색
    related_result = run_tool(
        "get_related_places",
        {
            "places": places,
        },
    )
    related_places = _extract_list(
        related_result,
        "related_places",
        "places",
        "results",
    )

    # 3. 이동 동선 정보 생성
    route_result = run_tool(
        "get_route_info",
        {
            "places": related_places,
            "transport_mode": transport_mode,
        },
    )
    route_summary = _extract_list(
        route_result,
        "route_segments",
        "route_summary",
        "routes",
    )

    # 4. 시간대별 일정표 구성
    daily_schedule = _build_daily_schedule(places, related_places)

    return {
        "tourist_spots": places,
        "related_places": related_places,
        "route_summary": route_summary,
        "daily_schedule": daily_schedule,
    }


def _build_daily_schedule(
    places: List[Dict[str, Any]],
    related_places: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Mock 장소 데이터를 기반으로 MVP용 시간대별 일정표를 만든다.
    """

    time_slots = [
        ("Day 1", "오전"),
        ("Day 1", "점심"),
        ("Day 1", "오후"),
        ("Day 1", "저녁"),
        ("Day 2", "오전"),
        ("Day 2", "점심"),
        ("Day 2", "오후"),
    ]

    schedule_places: List[Dict[str, Any]] = []

    # 기본 장소 먼저 추가
    schedule_places.extend(places)

    # 연관 장소도 추가
    for item in related_places:
        related_name = item.get("related_place")
        if related_name:
            schedule_places.append(
                {
                    "name": related_name,
                    "reason": item.get(
                        "relation_reason",
                        "기존 여행지와 함께 방문하기 좋은 연관 장소입니다.",
                    ),
                }
            )

    schedule: List[Dict[str, Any]] = []

    for index, place in enumerate(schedule_places[: len(time_slots)]):
        day, time_slot = time_slots[index]

        place_name = _get_place_name(place)

        schedule.append(
    {
        "day": day,
        "time_slot": time_slot,

        # 기존 테스트 호환용
        "place": place_name,

        # Step 6 출력 포맷용
        "place_name": place_name,

        "reason": place.get(
            "reason",
            "사용자 취향과 여행 조건을 고려해 추천한 장소입니다.",
        ),
        "route_memo": place.get(
            "route_memo",
            "이전 장소와의 이동 동선을 고려해 배치했습니다.",
        ),
    }
)

    return schedule