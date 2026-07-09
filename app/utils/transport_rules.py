import math


def estimate_public_transport_time(car_minutes: int) -> int:
    """
    자동차 기준 소요시간을 바탕으로 대중교통 예상 소요시간을 추정합니다.
    MVP에서는 실시간 환승 API를 사용하지 않으므로 참고용 값입니다.
    """

    return math.ceil(car_minutes * 1.7)


def estimate_public_transport_fee(distance_km: float, people_count: int = 1) -> int:
    """
    거리 기반 대중교통 요금을 추정합니다.
    기본요금 1,550원, 10km 초과 시 5km 단위로 100원씩 가산하는 단순 MVP 규칙입니다.
    """

    base_fee = 1550

    if distance_km <= 10:
        fee_per_person = base_fee
    else:
        extra_distance = distance_km - 10
        extra_units = math.ceil(extra_distance / 5)
        fee_per_person = base_fee + extra_units * 100

    return fee_per_person * people_count


def estimate_transport_cost(
    transport_mode: str,
    distance_km: float,
    car_minutes: int,
    taxi_fare: int | None,
    people_count: int,
) -> dict:
    """
    이동수단별 교통비와 예상 시간을 계산합니다.
    """

    if transport_mode == "택시":
        return {
            "transport_mode": transport_mode,
            "estimated_time_minutes": car_minutes,
            "estimated_cost": taxi_fare or 0,
            "is_estimated": False,
        }

    if transport_mode == "대중교통":
        return {
            "transport_mode": transport_mode,
            "estimated_time_minutes": estimate_public_transport_time(car_minutes),
            "estimated_cost": estimate_public_transport_fee(distance_km, people_count),
            "is_estimated": True,
        }

    if transport_mode in ["자차", "렌터카"]:
        return {
            "transport_mode": transport_mode,
            "estimated_time_minutes": car_minutes,
            "estimated_cost": 0,
            "is_estimated": True,
        }

    return {
        "transport_mode": transport_mode,
        "estimated_time_minutes": car_minutes,
        "estimated_cost": 0,
        "is_estimated": True,
    }