from typing import Any, Dict, List

from pydantic import BaseModel


class TripPlanResponse(BaseModel):
    """
    TripRoute 여행 일정 생성 응답 스키마입니다.
    """

    condition_summary: Dict[str, Any]
    daily_schedule: List[Dict[str, Any]]
    route_summary: List[Dict[str, Any]]
    cost_summary: Dict[str, Any]
    warnings: List[str]