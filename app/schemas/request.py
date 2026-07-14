from typing import Any, Optional

from pydantic import BaseModel, Field


class TripPlanRequest(BaseModel):
    """
    TripRoute 여행 일정 생성 요청 스키마입니다.
    """

    user_input: str = Field(
        ...,
        description="사용자의 자연어 여행 요청",
        examples=[
            "강릉으로 1박 2일 여행 가고 싶어. 바다랑 감성 카페, 먹거리를 좋아해."
        ],
    )

    transport_mode: str = Field(
        default="대중교통",
        description="이동수단: 자차, 렌터카, 대중교통, 택시",
    )

    people_count: int = Field(
        default=1,
        ge=1,
        description="여행 인원수",
    )

    previous_condition_summary: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "직전 턴의 condition_summary. 넘기면 후속 요청("
            "예: '카페 말고 맛집 위주로 바꿔줘')이 이전 조건을 이어받아 처리된다."
        ),
    )

    previous_result: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "직전 턴의 전체 결과(daily_schedule/route_summary 포함). 함께 넘기면 "
            "기간 연장 후속 요청(예: '3일로 늘려줘')에서 기존 일정을 유지한 채 "
            "늘어난 날짜만 새로 채운다."
        ),
    )