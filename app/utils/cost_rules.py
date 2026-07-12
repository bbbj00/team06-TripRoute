from typing import Any, Dict, List


def estimate_food_cost(people_count: int, days: int = 2) -> int:
    return 30000 * people_count * days


def estimate_cafe_cost(people_count: int, cafe_visits: int = 1) -> int:
    return 15000 * people_count * cafe_visits


def estimate_lodging_cost(people_count: int, nights: int = 1) -> int:
    return 50000 * people_count * nights


def estimate_admission_cost(people_count: int, places: List[Dict[str, Any]] | None = None) -> int:
    """
    MVP에서는 입장료 정보를 정교하게 파싱하지 않고 기본값으로 계산합니다.
    추후 TourAPI usefee + Upstage 구조화 추출로 대체합니다.
    """

    return 5000 * people_count


def build_cost_summary(
    transport_cost: int,
    people_count: int,
    days: int = 2,
    nights: int = 1,
    cafe_visits: int = 1,
    places: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    food = estimate_food_cost(people_count, days)
    cafe = estimate_cafe_cost(people_count, cafe_visits)
    lodging = estimate_lodging_cost(people_count, nights)
    admission = estimate_admission_cost(people_count, places)

    total = transport_cost + food + cafe + lodging + admission

    return {
        "transport": transport_cost,
        "food": food,
        "cafe": cafe,
        "lodging": lodging,
        "admission": admission,
        "total": total,
        "currency": "KRW",
    }