from app.core.config import settings
from app.services.solar import parse_trip_request
from app.services.upstage_client import _detect_city, _detect_prefer_local


def test_solar_parser_fallback_without_api_key(monkeypatch):
    # 테스트 실행 중에만 설정 객체의 API 키를 제거
    monkeypatch.setattr(
        settings,
        "UPSTAGE_API_KEY",
        "",
        raising=False,
    )

    result, warnings = parse_trip_request(
        "강릉으로 1박 2일 여행 가고 싶어. "
        "바다랑 감성 카페를 좋아해."
    )

    assert result["city"] == "강릉"
    assert result["duration"] == "1박 2일"
    assert result["_parser"] == "mock"
    assert result["prefer_local"] is False
    assert warnings


def test_solar_parser_fallback_detects_prefer_local(monkeypatch):
    monkeypatch.setattr(
        settings,
        "UPSTAGE_API_KEY",
        "",
        raising=False,
    )

    result, _ = parse_trip_request(
        "사람 안 몰리는 로컬 맛집 위주로 다니고 싶어."
    )

    assert result["prefer_local"] is True


def test_detect_prefer_local_keywords():
    assert _detect_prefer_local("현지인만 아는 숨은 명소로 가고 싶어") is True
    assert _detect_prefer_local("유명한 관광지 위주로 다니고 싶어") is False


def test_solar_parser_fallback_detects_other_city(monkeypatch):
    monkeypatch.setattr(
        settings,
        "UPSTAGE_API_KEY",
        "",
        raising=False,
    )

    result, _ = parse_trip_request("부산으로 2박 3일 여행 갈 거야.")

    assert result["city"] == "부산"


def test_detect_city_keywords():
    assert _detect_city("부산으로 여행 가고 싶어") == "부산"
    assert _detect_city("몽골로 여행 가고 싶어") is None