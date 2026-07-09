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