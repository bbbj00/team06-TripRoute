# app/agents/financial.py

from typing import Any, Dict

from app.utils.transport_rules import estimate_transport_cost


def build_financial_summary(
    route_plan: Dict[str, Any],
    transport_mode: str,
    people_count: int,
) -> Dict[str, Any]:
    """
    교통비, 식비, 카페비, 입장료, 숙박비, 총액을 계산한다.
    """

    route_summary = route_plan.get("route_summary", [])

    transport_cost = 0

    for route in route_summary:
        result = estimate_transport_cost(
            distance_km=route.get("distance_km", 0),
            car_minutes=route.get("car_minutes", 0),
            transport_mode=transport_mode,
            people_count=people_count,
            travel_days=2,
            taxi_fare=route.get("taxi_fare"),
        )
        transport_cost += result.get("estimated_cost", 0)

    food_cost = 30000 * people_count
    cafe_cost = 15000 * people_count
    admission_cost = 10000 * people_count
    lodging_cost = 100000

    total_cost = (
        transport_cost
        + food_cost
        + cafe_cost
        + admission_cost
        + lodging_cost
    )

    return {
    # 기존 테스트 호환용
    "total": total_cost,

    # Step 6 출력 포맷용
    "transport_cost": transport_cost,
    "food_cost": food_cost,
    "cafe_cost": cafe_cost,
    "admission_cost": admission_cost,
    "lodging_cost": lodging_cost,
    "total_cost": total_cost,

    "currency": "KRW",
    "is_estimated": True,
}