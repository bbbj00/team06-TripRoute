from app.services.upstage_client import parse_trip_request


def test_solar_parser_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("UPSTAGE_API_KEY", raising=False)

    result, warnings = parse_trip_request(
        "강릉으로 1박 2일 여행 가고 싶어. 바다랑 감성 카페를 좋아해."
    )

    assert result["city"] == "강릉"
    assert result["duration"] == "1박 2일"
    assert result["_parser"] == "mock"
    assert len(warnings) >= 1