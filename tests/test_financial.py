from app.utils.cost_rules import build_cost_summary
from app.utils.transport_rules import (
    estimate_public_transport_fee,
    estimate_public_transport_time,
    estimate_transport_cost,
    recommend_vehicle_by_people,
    estimate_rental_car_cost,
)


def test_public_transport_time_is_longer_than_car_time():
    car_minutes = 20

    result = estimate_public_transport_time(car_minutes)

    assert result > car_minutes


def test_public_transport_fee_positive():
    fee = estimate_public_transport_fee(distance_km=12.0, people_count=2)

    assert fee > 0


def test_transport_cost_public_transport():
    result = estimate_transport_cost(
        transport_mode="대중교통",
        distance_km=12.0,
        car_minutes=20,
        taxi_fare=12000,
        people_count=2,
    )

    assert result["transport_mode"] == "대중교통"
    assert result["estimated_cost"] > 0
    assert result["is_estimated"] is True


def test_transport_cost_taxi_uses_taxi_fare():
    result = estimate_transport_cost(
        transport_mode="택시",
        distance_km=12.0,
        car_minutes=20,
        taxi_fare=12000,
        people_count=2,
    )

    assert result["estimated_cost"] == 12000
    assert result["is_estimated"] is False


def test_build_cost_summary_total():
    summary = build_cost_summary(
        transport_cost=12000,
        people_count=2,
        days=2,
        nights=1,
        cafe_visits=1,
    )

    assert summary["transport"] == 12000
    assert summary["total"] > summary["transport"]
    assert summary["currency"] == "KRW"

    from app.utils.transport_rules import recommend_vehicle_by_people, estimate_rental_car_cost


def test_recommend_vehicle_by_people():
    result = recommend_vehicle_by_people(people_count=4)

    assert result["vehicle_type"] == "중형차"
    assert result["daily_rental_fee"] == 80000


def test_rental_car_cost_by_days():
    result = estimate_rental_car_cost(
        people_count=2,
        travel_days=2,
    )

    assert result["vehicle_type"] == "소형차"
    assert result["rental_cost"] == 120000