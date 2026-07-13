import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class TripRouteState(TypedDict, total=False):
    """
    TripRoute LangGraph Workflow에서 사용하는 공통 State입니다.

    각 노드(Agent)는 이 State를 읽고, 자신이 갱신할 필드만 담은 dict를 반환합니다.
    warnings/react_trace는 노드마다 새로 만든 리스트가 기존 값 뒤에 이어 붙도록
    (operator.add) 선언되어 있고, 나머지 필드는 마지막으로 쓴 값으로 교체됩니다.
    """

    # 사용자 입력
    user_input: str
    transport_mode: str
    people_count: int

    # Solar 파싱 결과 (parse_trip_request)
    city: str
    season: str
    duration: str
    travel_style: List[str]
    schedule_intensity: str
    prefer_local: bool
    prefer_budget: bool
    is_peak_season: bool
    parser: str

    # Route Planner 결과 (build_route_plan)
    candidate_places: List[Dict[str, Any]]
    rag_ranked_places: List[Dict[str, Any]]
    related_places: List[Dict[str, Any]]
    selected_places: List[Dict[str, Any]]
    route_summary: List[Dict[str, Any]]
    daily_schedule: List[Dict[str, Any]]
    lodging_place: Optional[Dict[str, Any]]
    data_source: str

    # Financial 결과 (build_financial_summary)
    cost_summary: Dict[str, Any]

    # 공통 누적 필드 (노드마다 이어 붙음)
    warnings: Annotated[List[str], operator.add]
    react_trace: Annotated[List[Dict[str, Any]], operator.add]

    # 최종 조립 결과 (finalize 노드에서 채움)
    result: Dict[str, Any]
