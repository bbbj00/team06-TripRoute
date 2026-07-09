from typing import Any, Dict, List, TypedDict


class TripRouteState(TypedDict):
    """
    TripRoute LangGraph Workflow에서 사용하는 공통 State입니다.

    각 Agent는 이 State를 읽고 필요한 값을 추가하거나 수정합니다.
    """

    # 사용자 입력 및 파싱 결과
    user_input: str
    city: str
    season: str
    duration: str
    travel_style: List[str]
    transport_mode: str
    people_count: int

    # 관광지 추천 관련 데이터
    candidate_places: List[Dict[str, Any]]
    rag_ranked_places: List[Dict[str, Any]]
    related_places: List[Dict[str, Any]]

    # 동선 정보
    route_segments: List[Dict[str, Any]]

    # 최종 결과
    daily_schedule: List[Dict[str, Any]]
    cost_summary: Dict[str, Any]
    warnings: List[str]