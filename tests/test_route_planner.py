import app.agents.route_planner as route_planner
from app.agents.route_planner import (
    _build_taste_text,
    _build_time_slots,
    _check_daily_density,
    _fetch_lodging_fee,
    _filter_places_within_radius,
    _haversine_km,
    _normalize_rag_place,
    _search_lodging_place,
    _sort_by_prefer_local,
    _sort_by_rating_desc,
)


def test_build_taste_text_includes_prefer_local_phrase():
    assert "로컬" in _build_taste_text(["바다", "감성 카페"], prefer_local=True)
    assert "로컬" not in _build_taste_text(["바다", "감성 카페"], prefer_local=False)


def test_haversine_km_same_point_is_zero():
    assert _haversine_km(37.5, 128.9, 37.5, 128.9) == 0


def test_haversine_km_known_distance_seoul_busan():
    # 서울시청(37.5665, 126.9780) - 부산시청(35.1796, 129.0756), 실제 직선거리는 약 325km
    distance = _haversine_km(37.5665, 126.9780, 35.1796, 129.0756)
    assert 300 < distance < 350


def test_filter_places_within_radius_excludes_far_place():
    places = [
        {"name": "안목해변", "latitude": 37.7712, "longitude": 128.9471},
        {"name": "경포대(근처)", "latitude": 37.7960, "longitude": 128.8965},  # 약 5km
        {"name": "부산(멀리)", "latitude": 35.1796, "longitude": 129.0756},  # 약 300km+
    ]

    result = _filter_places_within_radius(places, max_distance_km=15.0)

    names = {p["name"] for p in result}
    assert "안목해변" in names
    assert "경포대(근처)" in names
    assert "부산(멀리)" not in names


def test_filter_places_within_radius_keeps_places_without_coordinates():
    places = [
        {"name": "A", "latitude": 37.7712, "longitude": 128.9471},
        {"name": "B", "latitude": None, "longitude": None},
    ]

    result = _filter_places_within_radius(places, max_distance_km=15.0)

    assert {p["name"] for p in result} == {"A", "B"}


def test_filter_places_within_radius_with_anchor_only_returns_new_matches():
    # anchor_places(이미 확정된 후보 군집)를 기준으로 related_places만 걸러야 하며,
    # 반환값에 anchor_places 자체가 다시 섞여 나오면 안 됨
    anchor_places = [
        {"name": "안목해변", "latitude": 37.7712, "longitude": 128.9471},
    ]
    candidates = [
        {"name": "경포대(근처)", "latitude": 37.7960, "longitude": 128.8965},  # 약 5km
        {"name": "부산(멀리)", "latitude": 35.1796, "longitude": 129.0756},  # 300km+
    ]

    result = _filter_places_within_radius(
        candidates,
        max_distance_km=15.0,
        anchor_places=anchor_places,
    )

    names = {p["name"] for p in result}
    assert names == {"경포대(근처)"}
    assert "안목해변" not in names


def test_sort_by_prefer_local_ascending_when_true():
    places = [
        _normalize_rag_place({"title": "A", "review_count": 500}, "reason"),
        _normalize_rag_place({"title": "B", "review_count": 10}, "reason"),
        _normalize_rag_place({"title": "C", "review_count": 100}, "reason"),
    ]

    result = _sort_by_prefer_local(places, prefer_local=True)

    assert [p["name"] for p in result] == ["B", "C", "A"]


def test_sort_by_prefer_local_descending_when_false():
    places = [
        _normalize_rag_place({"title": "A", "review_count": 10}, "reason"),
        _normalize_rag_place({"title": "B", "review_count": 500}, "reason"),
    ]

    result = _sort_by_prefer_local(places, prefer_local=False)

    assert [p["name"] for p in result] == ["B", "A"]


def test_sort_by_prefer_local_places_missing_review_count_last():
    places = [
        _normalize_rag_place({"title": "없음"}, "reason"),
        _normalize_rag_place({"title": "있음", "review_count": 5}, "reason"),
    ]

    result = _sort_by_prefer_local(places, prefer_local=True)

    assert result[0]["name"] == "있음"
    assert result[1]["name"] == "없음"


def test_build_route_plan_uses_rag_result_when_available(monkeypatch):
    fake_results = [
        {
            "content_id": "1",
            "title": "테스트 관광지",
            "address": "강원특별자치도 강릉시",
            "rating": 4.5,
            "review_count": 100,
            "category": "관광지",
        }
    ]

    monkeypatch.setattr(
        route_planner,
        "retrieve_places_by_taste",
        lambda *args, **kwargs: fake_results,
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_common",
        lambda content_id: {
            "mapx": "128.9",
            "mapy": "37.7",
            "lDongRegnCd": "51",
            "lDongSignguCd": "150",
            "addr1": "강원특별자치도 강릉시",
        },
    )
    monkeypatch.setattr(
        route_planner,
        "get_route",
        lambda origin, destination: {},
    )
    monkeypatch.setattr(
        route_planner,
        "summarize_route",
        lambda route: {
            "distance_km": 1.0,
            "duration_min": 10,
            "taxi_fare": 5000,
            "toll_fare": 0,
        },
    )
    monkeypatch.setattr(
        route_planner,
        "get_course_content_ids",
        lambda city, **kwargs: [],
    )

    result = route_planner.build_route_plan(
        parsed={
            "city": "강릉",
            "duration": "1박 2일",
            "travel_style": ["바다"],
            "prefer_local": False,
            "schedule_intensity": "여유로운 일정",
        },
        transport_mode="대중교통",
        people_count=2,
    )

    assert result["data_source"] == "rag"
    assert len(result["rag_ranked_places"]) == 1
    assert result["rag_ranked_places"][0]["review_count"] == 100
    assert result["selected_places"][0]["latitude"] == 37.7


def test_search_course_related_places_matches_selected_place(monkeypatch):
    candidate_places = [{"content_id": "127722", "name": "안목해변"}]

    monkeypatch.setattr(
        route_planner,
        "get_course_content_ids",
        lambda city, **kwargs: ["2721490"],
    )
    # 실제 디스크 캐시(data/cache/)를 안 건드리도록 캐싱을 우회하고 fetch_fn을 바로 호출하게 함
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: [
            {"subcontentid": "127722", "subname": "안목해변"},
            {"subcontentid": "128758", "subname": "정동진"},
            {"subcontentid": "585522", "subname": "정동진해변"},
        ],
    )

    related_places, warnings = route_planner._search_course_related_places(
        candidate_places=candidate_places,
        city="강릉",
        max_related_places=5,
    )

    assert not warnings
    assert {p["name"] for p in related_places} == {"정동진", "정동진해변"}


def test_search_course_related_places_no_match_returns_empty(monkeypatch):
    candidate_places = [{"content_id": "999999", "name": "매칭 안 되는 장소"}]

    monkeypatch.setattr(
        route_planner,
        "get_course_content_ids",
        lambda city, **kwargs: ["2721490"],
    )
    # 실제 디스크 캐시(data/cache/)를 안 건드리도록 캐싱을 우회하고 fetch_fn을 바로 호출하게 함
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: [
            {"subcontentid": "127722", "subname": "안목해변"},
        ],
    )

    related_places, warnings = route_planner._search_course_related_places(
        candidate_places=candidate_places,
        city="강릉",
        max_related_places=5,
    )

    assert related_places == []
    assert not warnings


def test_search_course_related_places_excludes_far_subnum(monkeypatch):
    # 5일 코스 가정: 매칭된 장소(index 2)에서 COURSE_NEARBY_WINDOW(2)를 넘는 index 5, 6은
    # 다른 날짜 구간일 가능성이 높으므로 추천 대상에서 빠져야 함
    candidate_places = [{"content_id": "2", "name": "매칭 장소"}]

    monkeypatch.setattr(
        route_planner,
        "get_course_content_ids",
        lambda city, **kwargs: ["course-1"],
    )
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: [
            {"subcontentid": "0", "subname": "1일차-1"},
            {"subcontentid": "1", "subname": "1일차-2"},
            {"subcontentid": "2", "subname": "매칭 장소"},
            {"subcontentid": "3", "subname": "2일차-1"},
            {"subcontentid": "4", "subname": "2일차-2"},
            {"subcontentid": "5", "subname": "4일차-1"},
            {"subcontentid": "6", "subname": "5일차-1"},
        ],
    )

    related_places, warnings = route_planner._search_course_related_places(
        candidate_places=candidate_places,
        city="강릉",
        max_related_places=10,
    )

    assert not warnings
    names = {p["name"] for p in related_places}
    assert names == {"1일차-1", "1일차-2", "2일차-1", "2일차-2"}
    assert "4일차-1" not in names
    assert "5일차-1" not in names


def test_build_time_slots_drops_evening_in_winter():
    normal = _build_time_slots(1, "여유로운 일정", season="여름")
    winter = _build_time_slots(1, "여유로운 일정", season="겨울")

    assert ("Day 1", "저녁") in normal
    assert ("Day 1", "저녁") not in winter
    assert len(winter) < len(normal)


def test_build_time_slots_season_default_unaffected():
    default_slots = _build_time_slots(1, "여유로운 일정")
    summer_slots = _build_time_slots(1, "여유로운 일정", season="여름")

    assert default_slots == summer_slots


def test_check_daily_density_warns_when_over_relaxed_limit():
    daily_schedule = [
        {"day": "Day 1", "place": "A"},
        {"day": "Day 1", "place": "B"},
    ]
    route_summary = [{"estimated_time_minutes": 200}]  # 180분 기준 초과

    warnings = _check_daily_density(daily_schedule, route_summary, "여유로운 일정")

    assert len(warnings) == 1
    assert "Day 1" in warnings[0]


def test_check_daily_density_no_warning_within_limit():
    daily_schedule = [
        {"day": "Day 1", "place": "A"},
        {"day": "Day 1", "place": "B"},
    ]
    route_summary = [{"estimated_time_minutes": 30}]

    warnings = _check_daily_density(daily_schedule, route_summary, "여유로운 일정")

    assert warnings == []


def test_check_daily_density_packed_has_higher_threshold():
    daily_schedule = [
        {"day": "Day 1", "place": "A"},
        {"day": "Day 1", "place": "B"},
    ]
    route_summary = [{"estimated_time_minutes": 200}]  # 여유 기준(180)은 넘지만 빡빡 기준(300)은 안 넘음

    relaxed_warnings = _check_daily_density(daily_schedule, route_summary, "여유로운 일정")
    packed_warnings = _check_daily_density(daily_schedule, route_summary, "빡빡한 일정")

    assert len(relaxed_warnings) == 1
    assert packed_warnings == []


def test_sort_by_rating_desc_places_missing_rating_last():
    places = [
        _normalize_rag_place({"title": "없음"}, "reason"),
        _normalize_rag_place({"title": "5점", "rating": 5}, "reason"),
        _normalize_rag_place({"title": "3점", "rating": 3}, "reason"),
    ]

    result = _sort_by_rating_desc(places)

    assert [p["name"] for p in result] == ["5점", "3점", "없음"]


def test_fetch_lodging_fee_ignores_zero_registered_fee(monkeypatch):
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: [
            {"roommaxcount": "2", "roomoffseasonminfee1": "0"},
            {"roommaxcount": "2", "roomoffseasonminfee1": "30000"},
        ],
    )

    assert _fetch_lodging_fee("test-content-id", people_count=2, use_peak_season=False) == 30000


def test_search_lodging_place_picks_highest_rating_by_default(monkeypatch):
    monkeypatch.setattr(
        route_planner,
        "retrieve_places_by_taste",
        lambda *args, **kwargs: [
            {
                "content_id": "a", "title": "A호텔", "category": "숙박",
                "rating": 3, "review_count": 10, "address": "강원특별자치도 강릉시",
            },
            {
                "content_id": "b", "title": "B호텔", "category": "숙박",
                "rating": 5, "review_count": 20, "address": "강원특별자치도 강릉시",
            },
        ],
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_common",
        lambda content_id: {
            "mapx": "128.9", "mapy": "37.7",
            "lDongRegnCd": "51", "lDongSignguCd": "150",
            "addr1": "강원특별자치도 강릉시", "contenttypeid": "32",
        },
    )
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: [],  # 둘 다 요금 정보 없음 -> rating 기준으로만 판단
    )

    anchor_places = [{"latitude": 37.7, "longitude": 128.9}]

    result = _search_lodging_place(city="강릉", anchor_places=anchor_places)

    assert result["name"] == "B호텔"


def test_search_lodging_place_prefers_candidate_with_real_fee_data(monkeypatch):
    # B호텔이 평점은 더 높지만 요금 데이터가 없고, A호텔은 평점은 낮아도 실제 요금이 있음
    # -> Financial Agent가 추정치 대신 실측값을 쓸 수 있도록 A호텔을 골라야 함
    monkeypatch.setattr(
        route_planner,
        "retrieve_places_by_taste",
        lambda *args, **kwargs: [
            {
                "content_id": "a", "title": "A호텔", "category": "숙박",
                "rating": 3, "review_count": 10, "address": "강원특별자치도 강릉시",
            },
            {
                "content_id": "b", "title": "B호텔", "category": "숙박",
                "rating": 5, "review_count": 20, "address": "강원특별자치도 강릉시",
            },
        ],
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_common",
        lambda content_id: {
            "mapx": "128.9", "mapy": "37.7",
            "lDongRegnCd": "51", "lDongSignguCd": "150",
            "addr1": "강원특별자치도 강릉시", "contenttypeid": "32",
        },
    )
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: (
            [{"roommaxcount": "2", "roomoffseasonminfee1": "50000"}] if content_id == "a"
            else []  # B호텔은 요금 정보 없음
        ),
    )

    anchor_places = [{"latitude": 37.7, "longitude": 128.9}]

    result = _search_lodging_place(city="강릉", anchor_places=anchor_places)

    assert result["name"] == "A호텔"


def test_search_lodging_place_picks_cheapest_when_prefer_budget(monkeypatch):
    monkeypatch.setattr(
        route_planner,
        "retrieve_places_by_taste",
        lambda *args, **kwargs: [
            {
                "content_id": "a", "title": "A호텔", "category": "숙박",
                "rating": 5, "review_count": 10, "address": "강원특별자치도 강릉시",
            },
            {
                "content_id": "b", "title": "B호텔", "category": "숙박",
                "rating": 3, "review_count": 20, "address": "강원특별자치도 강릉시",
            },
        ],
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_common",
        lambda content_id: {
            "mapx": "128.9", "mapy": "37.7",
            "lDongRegnCd": "51", "lDongSignguCd": "150",
            "addr1": "강원특별자치도 강릉시", "contenttypeid": "32",
        },
    )
    monkeypatch.setattr(
        route_planner,
        "cached_call",
        lambda namespace, params, fetch_fn, ttl_seconds=None: fetch_fn(),
    )
    monkeypatch.setattr(
        route_planner,
        "get_detail_info",
        lambda content_id, content_type_id: (
            [{"roommaxcount": "2", "roomoffseasonminfee1": "80000"}] if content_id == "a"
            else [{"roommaxcount": "2", "roomoffseasonminfee1": "30000"}]
        ),
    )

    anchor_places = [{"latitude": 37.7, "longitude": 128.9}]

    result = _search_lodging_place(
        city="강릉",
        anchor_places=anchor_places,
        prefer_budget=True,
    )

    # rating은 A가 더 높지만, prefer_budget이면 실제 요금이 더 저렴한 B를 골라야 함
    assert result["name"] == "B호텔"
