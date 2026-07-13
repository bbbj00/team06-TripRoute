from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

from app.rag.retriever import retrieve_places_by_taste
from app.rag.vector_store import content_type_id_to_category
from app.services.kakao_mobility import get_route, summarize_route
from app.services.supabase_client import get_course_content_ids
from app.services.tour_api import (
    TourAPIError,
    get_detail_common,
    get_detail_info,
    search_keyword,
)
from app.tools.mock_tools import run_tool
from app.utils.cache import cached_call
from app.utils.cost_rules import estimate_lodging_fee_per_night
from app.utils.transport_rules import estimate_public_transport_time

COURSE_CONTENT_TYPE_ID = "25"
# 코스 하위 장소는 "몇 일차"인지 구분이 없어서, 매칭된 장소 기준 코스 내 순서(subnum)로
# 이 범위 안에 있는 것만 연관 장소로 추천함 (며칠짜리 코스든 상관없이 먼 구간이 섞이는 것 방지)
COURSE_NEARBY_WINDOW = 2

LODGING_CATEGORY = "숙박"
LODGING_CONTENT_TYPE_ID = "32"

RESTAURANT_CATEGORY = "음식점"
MEAL_TIME_SLOTS = {"점심", "저녁"}

EARTH_RADIUS_KM = 6371.0
# RAG는 취향 유사도만 보고 거리는 전혀 고려하지 않아서, 취향 1등이 해변이고 2등이 반대편
# 산간 지역이면 그대로 비효율적인 동선이 짜일 수 있음. 이미 선택된 후보들로부터 이 거리
# 이내인 곳만 다음 후보로 인정해서 지리적으로 뭉치게 만든다.
MAX_CANDIDATE_DISTANCE_KM = 15.0


Place = Dict[str, Any]
RouteSegment = Dict[str, Any]


def _get_observation(tool_result: Any) -> Any:
    if isinstance(tool_result, dict):
        return (
            tool_result.get("observation")
            or tool_result.get("output")
            or tool_result
        )

    if hasattr(tool_result, "observation"):
        return tool_result.observation

    if hasattr(tool_result, "output"):
        return tool_result.output

    return tool_result


def _extract_list(tool_result: Any, *keys: str) -> List[Dict[str, Any]]:
    observation = _get_observation(tool_result)

    if isinstance(observation, list):
        return observation

    if isinstance(observation, dict):
        for key in keys:
            value = observation.get(key)
            if isinstance(value, list):
                return value

        for value in observation.values():
            if isinstance(value, list):
                return value

    return []


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_rad, lon1_rad, lat2_rad, lon2_rad = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _filter_places_within_radius(
    places: List[Place],
    max_distance_km: float = MAX_CANDIDATE_DISTANCE_KM,
    anchor_places: List[Place] | None = None,
) -> List[Place]:
    """
    이미 선택된 장소들 중 하나에라도 max_distance_km 이내인 후보만 순서대로 추가한다
    (순차적 지리 군집화). RAG는 취향 유사도로만 순위를 매기고 거리는 안 보기 때문에,
    이 필터 없이는 취향 1등이 해변이고 2등이 반대편 산간 지역이어도 그대로 동선에
    들어가는 문제가 있었음.

    anchor_places를 넘기면 그 목록을 이미 확정된 군집 기준으로 삼아 places를 거르고
    (연관 관광지가 후보 군집과 동떨어지지 않게 하는 용도), 안 넘기면 places[0]을
    시작점으로 순차 군집을 새로 만든다(기존 RAG 후보 필터링 동작).

    좌표가 없는 장소(아직 _fill_missing_place_details 전이거나 조회 실패)는 거리
    판단이 불가능하므로 일단 포함시킨다 — 나중에 좌표가 채워지면 그 다음 판단에 반영됨.
    """

    if not places:
        return []

    if anchor_places is not None:
        selected: List[Place] = list(anchor_places)
        remaining = places
    else:
        selected = [places[0]]
        remaining = places[1:]

    for place in remaining:
        lat, lng = place.get("latitude"), place.get("longitude")

        if lat is None or lng is None:
            selected.append(place)
            continue

        located_selected = [
            s for s in selected
            if s.get("latitude") is not None and s.get("longitude") is not None
        ]

        if not located_selected:
            # 아직 좌표를 아는 후보가 하나도 없으면 거리 비교 자체가 불가능하니 통과시킨다
            selected.append(place)
            continue

        is_close_to_any = any(
            _haversine_km(lat, lng, s["latitude"], s["longitude"]) <= max_distance_km
            for s in located_selected
        )
        if is_close_to_any:
            selected.append(place)

    if anchor_places is not None:
        # anchor_places는 이미 확정된 목록이니, 그중에서 새로 통과한 것만 돌려준다
        return selected[len(anchor_places):]

    return selected


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_place_name(place: Place) -> str:
    return str(
        place.get("name")
        or place.get("place_name")
        or place.get("title")
        or place.get("related_place")
        or place.get("base_place")
        or "장소명 없음"
    ).strip()


def _format_place_signal(rating: Any, review_count: Any) -> str:
    """평점/리뷰수를 추천 이유 앞에 붙일 문장 조각으로 만든다. 둘 다 없으면 빈 문자열."""
    rating_value = _to_float(rating)

    if rating_value is not None and review_count is not None:
        return f"리뷰 {int(review_count):,}개, 평점 {rating_value:g}의 "
    if review_count is not None:
        return f"리뷰 {int(review_count):,}개의 "
    if rating_value is not None:
        return f"평점 {rating_value:g}의 "
    return ""


# 이 리뷰수 이상이면 추천 이유에 "인기"를 붙인다 (임의 기준 — 별도 통계적 근거는 없음)
POPULAR_REVIEW_COUNT_THRESHOLD = 300


def _build_place_reason(
    category: str | None,
    rating: Any,
    review_count: Any,
    travel_style: List[str],
) -> str:
    """
    장소의 카테고리·평점·리뷰수를 반영해 추천 이유를 장소별로 다르게 만든다.
    (기존에는 검색 배치 전체에 동일한 문자열을 재사용해 모든 장소의 추천 이유가 똑같았음)
    """
    category_text = category or "관광지"
    style_text = ", ".join(travel_style) if travel_style else "여행"
    signal = _format_place_signal(rating, review_count)

    review_count_value = review_count if isinstance(review_count, (int, float)) else 0
    popularity_prefix = "인기 " if review_count_value >= POPULAR_REVIEW_COUNT_THRESHOLD else ""

    return (
        f"{signal}{popularity_prefix}{category_text}인 곳으로, "
        f"{style_text} 취향에 잘 맞습니다."
    )


def _normalize_tour_place(
    item: Dict[str, Any],
    source: str,
    travel_style: List[str],
) -> Place:
    """
    TourAPI searchKeyword2 결과를 Route Planner 내부 형식으로 변환한다.
    """
    title = str(item.get("title") or "장소명 없음").strip()
    category = content_type_id_to_category(item.get("contenttypeid"))

    return {
        "name": title,
        "title": title,
        "content_id": item.get("contentid"),
        "content_type_id": item.get("contenttypeid"),
        "address": item.get("addr1") or "",
        "longitude": _to_float(item.get("mapx")),
        "latitude": _to_float(item.get("mapy")),
        "area_code": item.get("lDongRegnCd") or item.get("areacode"),
        "signgu_code": (
            item.get("lDongSignguCd")
            or item.get("sigungucode")
        ),
        "image_url": item.get("firstimage") or "",
        "reason": _build_place_reason(category, None, None, travel_style),
        "source": source,
        "category": category,
        "rating": None,
        "review_count": None,
        "raw": item,
    }


def _build_taste_text(travel_style: List[str], prefer_local: bool) -> str:
    style_text = ", ".join(travel_style) if travel_style else "여행"

    if prefer_local:
        return f"{style_text}을(를) 좋아하고, 사람이 많이 몰리지 않는 로컬 분위기의 장소"

    return f"{style_text}을(를) 좋아하는 여행"


def _normalize_rag_place(item: Dict[str, Any], travel_style: List[str]) -> Place:
    """
    match_places RPC 결과(Supabase places 테이블 행)를 Route Planner 내부 형식으로 변환한다.

    Supabase places 테이블에는 좌표(위도/경도)가 없어서 longitude/latitude는 일단 None으로
    두고, 이후 _fill_missing_place_details()에서 TourAPI로 보완한다.
    """
    title = str(item.get("title") or "장소명 없음").strip()
    category = item.get("category")
    rating = item.get("rating")
    review_count = item.get("review_count")

    return {
        "name": title,
        "title": title,
        "content_id": item.get("content_id"),
        "address": item.get("address") or "",
        "longitude": None,
        "latitude": None,
        "area_code": None,
        "signgu_code": None,
        "image_url": "",
        "reason": _build_place_reason(category, rating, review_count, travel_style),
        "source": "rag",
        "rating": rating,
        "review_count": review_count,
        "category": category,
        "similarity": item.get("similarity"),
        "raw": item,
    }


def _sort_by_prefer_local(places: List[Place], prefer_local: bool) -> List[Place]:
    """
    prefer_local이 켜져 있으면 review_count가 적은(덜 알려진) 곳을 우선하고,
    아니면 review_count가 많은(유명한) 곳을 우선한다. review_count가 없는(Google Places
    매칭 실패) 곳은 정보 없음으로 취급해 배제하지 않고 뒤쪽에 배치한다.
    """

    def sort_key(place: Place) -> Tuple[int, int]:
        review_count = place.get("review_count")
        if review_count is None:
            return (1, 0)

        return (0, review_count if prefer_local else -review_count)

    return sorted(places, key=sort_key)


def _fill_missing_place_details(places: List[Place]) -> List[Place]:
    """
    RAG 결과는 좌표/지역코드가 없으므로, 동선 계산과 연관 관광지 조회에 필요한
    mapx/mapy(좌표)·lDongRegnCd/lDongSignguCd(지역코드)를 TourAPI로 보완한다.
    코스 하위 장소(_normalize_course_sub_place)는 category도 없어서 같이 채운다
    (Financial Agent가 카테고리로 usefee/숙박 요금 조회 대상을 판단하는 데 필요).
    """

    for place in places:
        if place.get("latitude") is not None and place.get("longitude") is not None:
            continue

        content_id = place.get("content_id")
        if not content_id:
            continue

        try:
            detail = get_detail_common(content_id)
        except TourAPIError:
            continue

        place["latitude"] = _to_float(detail.get("mapy"))
        place["longitude"] = _to_float(detail.get("mapx"))
        place["area_code"] = detail.get("lDongRegnCd") or detail.get("areacode")
        place["signgu_code"] = (
            detail.get("lDongSignguCd") or detail.get("sigungucode")
        )
        if not place.get("address"):
            place["address"] = detail.get("addr1") or ""
        if not place.get("image_url"):
            place["image_url"] = detail.get("firstimage") or ""
        if not place.get("category"):
            place["category"] = content_type_id_to_category(detail.get("contenttypeid"))

    return places


def _search_rag_places(
    city: str,
    travel_style: List[str],
    prefer_local: bool,
    max_places: int,
) -> List[Place]:
    """
    Supabase RAG(pgvector 유사도 검색)로 도시 내 취향 매칭 관광지를 가져온다.
    실패하거나 결과가 없으면 빈 리스트를 반환해 호출자가 TourAPI 실시간 검색으로
    넘어갈 수 있게 한다.
    """

    taste_text = _build_taste_text(travel_style, prefer_local)

    try:
        results = retrieve_places_by_taste(
            taste_text,
            match_count=max(max_places * 3, 10),
            city=city,
        )
    except Exception:
        return []

    if not results:
        return []

    places = _deduplicate_places(
        [_normalize_rag_place(item, travel_style) for item in results]
    )

    return _sort_by_prefer_local(places, prefer_local)


def _sort_by_rating_desc(places: List[Place]) -> List[Place]:
    """
    rating이 높은 순으로 정렬한다. rating이 없는(Google Places 매칭 실패) 곳은
    배제하지 않고 뒤쪽에 배치한다 (_sort_by_prefer_local과 동일한 None 처리 방식).
    """

    def sort_key(place: Place) -> Tuple[int, float]:
        rating = place.get("rating")
        if rating is None:
            return (1, 0.0)
        return (0, -rating)

    return sorted(places, key=sort_key)


def _fetch_lodging_fee(
    content_id: str,
    people_count: int,
    use_peak_season: bool,
) -> int | None:
    """
    숙박 후보의 실제 1박 요금을 조회한다. 계산 로직(인원수/성수기 반영)은
    cost_rules.estimate_lodging_fee_per_night에 있고 — Financial Agent와 동일한
    로직을 재사용해서 선택 시점과 최종 청구 시점의 판단이 어긋나지 않게 함 —
    여기서는 TourAPI 조회 + 캐싱만 담당한다. 캐시 namespace/params를 Financial
    Agent와 동일하게 맞춰서 같은 응답을 재사용한다(중복 호출 방지).
    """

    try:
        rooms = cached_call(
            namespace="detail_info_lodging",
            params={"content_id": content_id, "content_type_id": LODGING_CONTENT_TYPE_ID},
            fetch_fn=lambda: get_detail_info(content_id, LODGING_CONTENT_TYPE_ID),
            ttl_seconds=60 * 60 * 24,
        )
    except TourAPIError:
        return None

    return estimate_lodging_fee_per_night(rooms, people_count, use_peak_season)


def _search_lodging_place(
    city: str,
    anchor_places: List[Place],
    prefer_budget: bool = False,
    people_count: int = 1,
    is_peak_season: bool = False,
    travel_style: List[str] | None = None,
) -> Place | None:
    """
    1박 이상 여행일 때 숙박 후보를 하나 골라서 반환한다. RAG로 "숙박/호텔" 관련
    장소를 검색한 뒤, 이미 선택된 관광지 군집(anchor_places)과 15km 이내인 곳들 중
    고른다 — prefer_budget(Coordinator가 "가성비" 같은 예산 중시 의도를 인식해서
    넘기는 신호)이 켜져 있으면 실제 요금이 가장 저렴한 곳을, 아니면 rating이 가장
    높은 곳을 우선한다.

    정렬 후에는 그중 **실제 요금 데이터가 있는 첫 번째 후보**를 우선 선택한다 —
    예를 들어 평점 1등이 TourAPI에 객실 요금을 등록 안 해뒀으면, 정보 없는 곳
    대신 요금 데이터가 있는 다음 순위를 골라서 Financial Agent가 추정치가 아닌
    실측값을 쓸 수 있게 한다(동점/전부 데이터 없음이면 원래 1등을 그대로 씀).
    후보가 없으면 None을 반환해 Financial Agent가 기본 추정치로 대체하게 한다.
    """

    try:
        results = retrieve_places_by_taste(
            "편안하고 접근성 좋은 숙박 시설, 호텔, 펜션",
            match_count=20,
            city=city,
        )
    except Exception:
        return None

    lodging_places = _deduplicate_places(
        [
            _normalize_rag_place(item, travel_style or [])
            for item in results
            if item.get("category") == LODGING_CATEGORY
        ]
    )
    if not lodging_places:
        return None

    lodging_places = _fill_missing_place_details(lodging_places)
    lodging_places = _filter_places_within_radius(
        lodging_places,
        anchor_places=anchor_places,
    )
    if not lodging_places:
        return None

    fees_by_content_id = {
        place["content_id"]: _fetch_lodging_fee(place["content_id"], people_count, is_peak_season)
        for place in lodging_places
        if place.get("content_id")
    }

    if prefer_budget:
        ranked = sorted(
            lodging_places,
            key=lambda place: (
                fee
                if (fee := fees_by_content_id.get(place.get("content_id"))) is not None
                else float("inf")
            ),
        )
    else:
        ranked = _sort_by_rating_desc(lodging_places)

    for place in ranked:
        if fees_by_content_id.get(place.get("content_id")) is not None:
            return place

    return ranked[0]


def _search_restaurant_places(
    city: str,
    anchor_places: List[Place],
    max_restaurants: int,
    travel_style: List[str],
    prefer_local: bool = False,
) -> List[Place]:
    """
    점심/저녁 시간대에 배정할 음식점 후보를 명시적으로 확보한다.

    _search_rag_places는 취향 텍스트 전체와의 유사도만으로 후보를 뽑기 때문에, 사용자가
    "먹거리"를 취향으로 꼽아도 관광지/카페 쪽 텍스트가 더 유사하면 후보 풀에 음식점이
    하나도 안 뽑힐 수 있다. _reorder_places_for_time_slots는 이미 뽑힌 후보 중에서만
    음식점을 골라 점심/저녁 슬롯에 배치하므로, 애초에 후보 풀에 음식점이 없으면 아무리
    슬롯 배정을 잘해도 식사 시간대에 관광지가 그대로 들어가는 문제가 있었다.
    (_search_lodging_place가 숙박 후보를 별도로 확보하는 것과 동일한 이유로,
    음식점도 "취향 유사도 최상위 후보"에만 의존하지 않고 카테고리로 직접 검색해서
    확보한다.)
    """
    if max_restaurants <= 0:
        return []

    taste_text = _build_taste_text(travel_style + ["맛집", "음식점"], prefer_local=False)

    try:
        results = retrieve_places_by_taste(
            taste_text,
            match_count=max(max_restaurants * 3, 10),
            city=city,
        )
    except Exception:
        return []

    restaurant_places = _deduplicate_places(
        [
            _normalize_rag_place(item, travel_style)
            for item in results
            if item.get("category") == RESTAURANT_CATEGORY
        ]
    )
    if not restaurant_places:
        return []

    restaurant_places = _fill_missing_place_details(restaurant_places)
    restaurant_places = _filter_places_within_radius(
        restaurant_places,
        anchor_places=anchor_places,
    )
    if not restaurant_places:
        return []

    restaurant_places = _sort_by_prefer_local(restaurant_places, prefer_local)

    return restaurant_places[:max_restaurants]


def _deduplicate_places(places: List[Place]) -> List[Place]:
    result: List[Place] = []
    seen: set[str] = set()

    for place in places:
        key = re.sub(r"\s+", "", _get_place_name(place)).lower()

        if not key or key == "장소명없음" or key in seen:
            continue

        seen.add(key)
        result.append(place)

    return result


def _parse_travel_days(duration: str) -> int:
    if "당일" in duration:
        return 1

    day_match = re.search(r"(\d+)\s*일", duration)
    if day_match:
        return max(1, int(day_match.group(1)))

    night_match = re.search(r"(\d+)\s*박", duration)
    if night_match:
        return max(1, int(night_match.group(1)) + 1)

    return 2


def _build_time_slots(
    travel_days: int,
    schedule_intensity: str,
    season: str = "",
) -> List[Tuple[str, str]]:
    """
    하루 일정의 시간대 슬롯을 만든다.

    관광지 슬롯(오전/오후, 빡빡한 일정은 "늦은 오후" 추가)의 개수는 일정 강도로
    정해진다 — 빡빡한 일정=3개, 그 외(보통/여유로운 일정)=2개. 점심/저녁 식당
    슬롯은 일정 강도와 무관하게 항상 포함한다(관광지 개수와 별개로 늘 챙김).

    겨울은 일조시간이 짧아 저녁 시간대 야외 일정이 부담스러우므로 저녁 슬롯을 뺀다.
    (계절이 몇 시에 해가 지는지까지 정밀 반영하긴 어려우니, "저녁 슬롯 유무"라는 단순한
    방식으로 근사함 — 봄/여름/가을은 기존과 동일)

    여행 마지막 날은 저녁 전에 귀가/이동하는 경우가 많아 저녁 슬롯을 뺀다.
    """
    is_short_daylight_season = "겨울" in season
    attraction_count = 3 if "빡빡" in schedule_intensity else 2

    def build_day_slots(include_dinner: bool) -> List[str]:
        slots = ["오전", "점심", "오후"]
        if attraction_count >= 3:
            slots.append("늦은 오후")
        if include_dinner:
            slots.append("저녁")
        return slots

    normal_slots = build_day_slots(include_dinner=not is_short_daylight_season)
    last_day_slots = build_day_slots(include_dinner=False)

    result: List[Tuple[str, str]] = []

    for day in range(1, travel_days + 1):
        slots = (
            last_day_slots
            if travel_days > 1 and day == travel_days
            else normal_slots
        )

        for time_slot in slots:
            result.append((f"Day {day}", time_slot))

    return result


def _search_real_places(
    city: str,
    max_places: int,
    travel_style: List[str],
) -> List[Place]:
    items = search_keyword(
        keyword=city,
        num_of_rows=max(10, max_places * 2),
        page_no=1,
    )

    return _deduplicate_places(
        [
            _normalize_tour_place(
                item=item,
                source="tour_api",
                travel_style=travel_style,
            )
            for item in items
        ]
    )


def _normalize_course_sub_place(sub_item: Dict[str, Any], base_name: str) -> Place:
    """
    detailInfo2(여행코스 하위 장소 목록) 응답 항목을 Route Planner 내부 형식으로 변환한다.
    """
    title = str(sub_item.get("subname") or "장소명 없음").strip()

    return {
        "name": title,
        "title": title,
        "content_id": sub_item.get("subcontentid"),
        "address": "",
        "longitude": None,
        "latitude": None,
        "area_code": None,
        "signgu_code": None,
        "image_url": sub_item.get("subdetailimg") or "",
        "reason": f"{base_name}과(와) 같은 여행 코스에 포함된 연관 관광지입니다.",
        "source": "course",
        "rating": None,
        "review_count": None,
        "category": None,
        "raw": sub_item,
    }


def _search_course_related_places(
    candidate_places: List[Place],
    city: str,
    max_related_places: int,
) -> Tuple[List[Place], List[str]]:
    """
    선택된 관광지 후보가 TourAPI 여행코스(contentTypeId=25)의 하위 장소로 포함돼 있으면,
    같은 코스의 다른 장소들을 연관 관광지로 추천한다.

    (T맵 내비게이션 기반 "관광지별 연관 관광지" API는 제공 기간이 2025년 4월까지로 만료돼
    더 이상 데이터가 없어서, 대신 관광공사가 직접 큐레이션한 여행코스 데이터를 활용한다.)
    """

    related_places: List[Place] = []
    warnings: List[str] = []

    try:
        course_content_ids = get_course_content_ids(city)
    except Exception as exc:
        warnings.append(f"{city}: 여행코스 목록 조회 실패 ({exc})")
        return [], warnings

    if not course_content_ids:
        return [], warnings

    candidate_ids = {
        str(place["content_id"])
        for place in candidate_places
        if place.get("content_id")
    }

    for course_id in course_content_ids:
        if len(related_places) >= max_related_places:
            break

        try:
            # 코스 구성은 관광공사가 큐레이션한 데이터라 자주 안 바뀌므로,
            # 요청마다 매번 재조회하지 않도록 길게(7일) 캐싱한다.
            sub_items = cached_call(
                namespace="course_detail_info",
                params={"content_id": course_id, "content_type_id": COURSE_CONTENT_TYPE_ID},
                fetch_fn=lambda cid=course_id: get_detail_info(cid, COURSE_CONTENT_TYPE_ID),
                ttl_seconds=60 * 60 * 24 * 7,
            )
        except TourAPIError as exc:
            warnings.append(f"여행코스 {course_id} 조회 실패: {exc}")
            continue

        matched_index = next(
            (
                i
                for i, item in enumerate(sub_items)
                if str(item.get("subcontentid")) in candidate_ids
            ),
            None,
        )
        if matched_index is None:
            continue

        base_name = str(sub_items[matched_index].get("subname") or "")

        # 코스 하위 장소 데이터에는 "몇 일차"인지 구분이 없고 순서(subnum)만 있어서,
        # 코스 전체를 추천하면 며칠짜리 코스든 상관없이 뒤쪽(다른 날짜용) 장소까지 섞여
        # 들어올 수 있음. 매칭된 장소 기준 코스 내 순서상 가까운 구간(앞뒤 COURSE_NEARBY_WINDOW개)
        # 만 근사치로 추천해서 이 문제를 줄인다.
        nearby_indexes = sorted(
            (
                i
                for i in range(len(sub_items))
                if i != matched_index
                and abs(i - matched_index) <= COURSE_NEARBY_WINDOW
            ),
            key=lambda i: abs(i - matched_index),
        )

        for i in nearby_indexes:
            if len(related_places) >= max_related_places:
                break

            related_places.append(_normalize_course_sub_place(sub_items[i], base_name))

    return _deduplicate_places(related_places), warnings


def _unavailable_route(
    origin_name: str,
    destination_name: str,
    transport_mode: str,
) -> RouteSegment:
    return {
        "from": origin_name,
        "to": destination_name,
        "origin": origin_name,
        "destination": destination_name,
        "distance_km": 0.0,
        "car_minutes": 0,
        "estimated_time_minutes": 0,
        "estimated_time": "조회 실패",
        "transport_mode": transport_mode,
        "taxi_fare": 0,
        "toll_fare": 0,
        "is_estimated": True,
        "data_source": "unavailable",
        "memo": "이동 경로를 조회하지 못했습니다.",
    }


def _build_real_routes(
    selected_places: List[Place],
    transport_mode: str,
) -> Tuple[List[RouteSegment], List[str]]:
    routes: List[RouteSegment] = []
    warnings: List[str] = []

    for index in range(len(selected_places) - 1):
        origin = selected_places[index]
        destination = selected_places[index + 1]

        origin_name = _get_place_name(origin)
        destination_name = _get_place_name(destination)

        origin_lon = origin.get("longitude")
        origin_lat = origin.get("latitude")
        destination_lon = destination.get("longitude")
        destination_lat = destination.get("latitude")

        if None in (
            origin_lon,
            origin_lat,
            destination_lon,
            destination_lat,
        ):
            warnings.append(
                f"{origin_name} → {destination_name}: 좌표가 없습니다."
            )
            routes.append(
                _unavailable_route(
                    origin_name,
                    destination_name,
                    transport_mode,
                )
            )
            continue

        try:
            route = get_route(
                origin=(float(origin_lon), float(origin_lat)),
                destination=(
                    float(destination_lon),
                    float(destination_lat),
                ),
            )
            summary = summarize_route(route)
        except Exception as exc:
            warnings.append(
                f"{origin_name} → {destination_name}: "
                f"Kakao 경로 조회 실패 ({exc})"
            )
            routes.append(
                _unavailable_route(
                    origin_name,
                    destination_name,
                    transport_mode,
                )
            )
            continue

        car_minutes = int(summary["duration_min"])
        display_minutes = (
            estimate_public_transport_time(car_minutes)
            if transport_mode == "대중교통"
            else car_minutes
        )

        routes.append(
            {
                "from": origin_name,
                "to": destination_name,
                "origin": origin_name,
                "destination": destination_name,
                "distance_km": float(summary["distance_km"]),
                "car_minutes": car_minutes,
                "estimated_time_minutes": display_minutes,
                "estimated_time": f"약 {display_minutes}분",
                "transport_mode": transport_mode,
                "taxi_fare": int(summary["taxi_fare"]),
                "toll_fare": int(summary["toll_fare"]),
                "is_estimated": transport_mode == "대중교통",
                "data_source": "kakao_mobility",
                "memo": (
                    f"{origin_name}에서 {destination_name}까지 "
                    f"{transport_mode}으로 이동합니다."
                ),
            }
        )

    return routes, warnings


def _reorder_places_for_time_slots(
    selected_places: List[Place],
    time_slots: List[Tuple[str, str]],
) -> List[Place]:
    """
    점심/저녁 시간대에는 음식점 카테고리 장소를 우선 배정한다.
    (기존에는 selected_places를 시간대와 순서대로 그대로 zip해서, 식사 시간대에
    식당이 아니라 검색 순서상 먼저 나온 아무 장소나 배치되는 문제가 있었음)

    장소 개수와 시간대 개수가 다를 수 있어 selected_places 길이 기준으로만 슬롯을 본다
    (_build_daily_schedule도 동일하게 앞쪽 len(selected_places)개 슬롯만 사용함).
    """
    meal_indexes = [
        index
        for index, (_, time_slot) in enumerate(time_slots[: len(selected_places)])
        if time_slot in MEAL_TIME_SLOTS
    ]

    food_places = [p for p in selected_places if p.get("category") == RESTAURANT_CATEGORY]
    other_places = [p for p in selected_places if p.get("category") != RESTAURANT_CATEGORY]

    ordered: List[Place | None] = [None] * len(selected_places)
    remaining_meal_indexes = list(meal_indexes)

    for place in food_places:
        if remaining_meal_indexes:
            ordered[remaining_meal_indexes.pop(0)] = place
        else:
            # 식사 시간대가 이미 다 찼으면 나머지 일반 시간대에 배치한다
            other_places.append(place)

    empty_indexes = [index for index, place in enumerate(ordered) if place is None]
    for index, place in zip(empty_indexes, other_places):
        ordered[index] = place

    return [place for place in ordered if place is not None]


def _build_daily_schedule(
    selected_places: List[Place],
    routes: List[RouteSegment],
    travel_days: int,
    schedule_intensity: str,
    travel_style: List[str],
    season: str = "",
) -> List[Dict[str, Any]]:
    time_slots = _build_time_slots(
        travel_days=travel_days,
        schedule_intensity=schedule_intensity,
        season=season,
    )

    schedule: List[Dict[str, Any]] = []

    for index, place in enumerate(selected_places[: len(time_slots)]):
        day, time_slot = time_slots[index]
        place_name = _get_place_name(place)

        if index == 0:
            route_memo = "여행의 첫 방문 장소입니다."
        elif index - 1 < len(routes):
            route = routes[index - 1]
            route_memo = (
                f"{route['from']}에서 "
                f"{route['estimated_time']} 이동합니다."
            )
        else:
            route_memo = "이전 장소와의 동선을 고려해 배치했습니다."

        reason = place.get("reason")
        if not reason:
            reason = (
                f"{', '.join(travel_style)} 취향을 고려한 장소입니다."
                if travel_style
                else "여행 조건을 고려한 장소입니다."
            )

        schedule.append(
            {
                "day": day,
                "time_slot": time_slot,
                "place": place_name,
                "place_name": place_name,
                "reason": reason,
                "route_memo": route_memo,
                "address": place.get("address", ""),
                "image_url": place.get("image_url", ""),
                "latitude": place.get("latitude"),
                "longitude": place.get("longitude"),
                "content_id": place.get("content_id"),
                "source": place.get("source"),
            }
        )

    return schedule


# 하루 이동시간 합이 이 기준(분)을 넘으면 과밀 경고를 남긴다. "여유로운 일정"을 골랐는데
# 실제로는 이동만으로 하루가 빠듯하면 사용자 기대와 어긋나므로, 일정 강도별로 다르게 잡음.
RELAXED_DAILY_TRAVEL_LIMIT_MIN = 180
PACKED_DAILY_TRAVEL_LIMIT_MIN = 300


def _check_daily_density(
    daily_schedule: List[Dict[str, Any]],
    route_summary: List[RouteSegment],
    schedule_intensity: str,
) -> List[str]:
    """
    하루 단위로 구간 이동시간 합을 계산해서, 일정 강도 기준을 넘으면 경고를 남긴다.
    장소별 체류시간 데이터가 없어 반영은 못 하고, 구간 이동시간만으로 근사 판단한다.

    route_summary[i]는 daily_schedule[i] -> daily_schedule[i+1] 구간이므로, 그 이동을
    도착지가 속한 날짜("day")의 이동시간으로 집계한다.
    """

    limit_minutes = (
        RELAXED_DAILY_TRAVEL_LIMIT_MIN
        if "여유" in schedule_intensity
        else PACKED_DAILY_TRAVEL_LIMIT_MIN
    )

    day_to_minutes: Dict[str, int] = {}
    for index, route in enumerate(route_summary):
        if index + 1 >= len(daily_schedule):
            continue

        day = daily_schedule[index + 1].get("day", "")
        day_to_minutes[day] = day_to_minutes.get(day, 0) + int(
            route.get("estimated_time_minutes", 0)
        )

    warnings: List[str] = []
    for day, minutes in day_to_minutes.items():
        if minutes > limit_minutes:
            warnings.append(
                f"{day}: 이동시간 합이 약 {minutes}분으로 '{schedule_intensity}' 기준보다 "
                "빡빡할 수 있습니다."
            )

    return warnings


def _build_mock_fallback(
    parsed: Dict[str, Any],
    transport_mode: str,
) -> Dict[str, Any]:
    city = parsed.get("city", "강릉")
    travel_style = parsed.get("travel_style", [])

    search_result = run_tool(
        "search_places",
        {
            "city": city,
            "travel_style": travel_style,
        },
    )
    places = _extract_list(
        search_result,
        "places",
        "tourist_spots",
        "results",
    )

    related_result = run_tool(
        "get_related_places",
        {"places": places},
    )
    related_places = _extract_list(
        related_result,
        "related_places",
        "places",
        "results",
    )

    route_result = run_tool(
        "get_route_info",
        {
            "places": related_places,
            "transport_mode": transport_mode,
        },
    )
    route_summary = _extract_list(
        route_result,
        "route_segments",
        "route_summary",
        "routes",
    )

    schedule_places: List[Place] = list(places)

    for item in related_places:
        related_name = item.get("related_place")
        if related_name:
            schedule_places.append(
                {
                    "name": related_name,
                    "reason": item.get(
                        "relation_reason",
                        "연관 관광지입니다.",
                    ),
                    "source": "mock",
                }
            )

    travel_days = _parse_travel_days(
        str(parsed.get("duration") or "1박 2일")
    )
    schedule_intensity = str(
        parsed.get("schedule_intensity") or "보통"
    )
    season = str(parsed.get("season") or "")
    time_slots = _build_time_slots(
        travel_days,
        schedule_intensity,
        season=season,
    )

    daily_schedule: List[Dict[str, Any]] = []

    for index, place in enumerate(schedule_places[: len(time_slots)]):
        day, time_slot = time_slots[index]
        name = _get_place_name(place)

        daily_schedule.append(
            {
                "day": day,
                "time_slot": time_slot,
                "place": name,
                "place_name": name,
                "reason": place.get(
                    "reason",
                    "여행 조건을 고려한 장소입니다.",
                ),
                "route_memo": place.get(
                    "route_memo",
                    "이전 장소와의 동선을 고려해 배치했습니다.",
                ),
                "source": "mock",
            }
        )

    return {
        "tourist_spots": places,
        "candidate_places": places,
        "rag_ranked_places": [],
        "related_places": related_places,
        "selected_places": schedule_places,
        "route_summary": route_summary,
        "route_segments": route_summary,
        "daily_schedule": daily_schedule,
        "warnings": [
            "실제 TourAPI 호출 실패 또는 검색 결과 없음으로 "
            "Mock 데이터를 사용했습니다."
        ],
        "data_source": "mock",
    }


def build_route_plan(
    parsed: Dict[str, Any],
    transport_mode: str,
    people_count: int,
) -> Dict[str, Any]:
    """
    Route Planner Agent.

    TourAPI 관광지 조회
    → 연관 관광지 조회
    → Kakao Mobility 경로 조회
    → 일정 생성
    → 실패 시 Mock fallback
    """

    city = str(parsed.get("city") or "강릉")
    duration = str(parsed.get("duration") or "1박 2일")
    travel_style = list(parsed.get("travel_style") or [])
    prefer_local = bool(parsed.get("prefer_local", False))
    prefer_budget = bool(parsed.get("prefer_budget", False))
    is_peak_season = bool(parsed.get("is_peak_season", False))
    schedule_intensity = str(
        parsed.get("schedule_intensity") or "보통"
    )
    season = str(parsed.get("season") or "")

    travel_days = _parse_travel_days(duration)
    time_slots = _build_time_slots(
        travel_days,
        schedule_intensity,
        season=season,
    )
    max_places = len(time_slots)

    rag_places = _search_rag_places(
        city=city,
        travel_style=travel_style,
        prefer_local=prefer_local,
        max_places=max_places,
    )

    if rag_places:
        candidate_places = _fill_missing_place_details(rag_places)
        data_source = "rag"
    else:
        try:
            candidate_places = _search_real_places(
                city=city,
                max_places=max_places,
                travel_style=travel_style,
            )
            data_source = "real_api"
        except Exception:
            return _build_mock_fallback(
                parsed=parsed,
                transport_mode=transport_mode,
            )

    # 취향 순위만으로 뽑으면 서로 멀리 떨어진 장소가 섞여 동선이 비효율적일 수 있어서,
    # 취향 1등 기준으로 지리적으로 뭉친 후보만 남긴다 (순위는 그대로 유지됨)
    candidate_places = _filter_places_within_radius(candidate_places)

    if not candidate_places:
        return _build_mock_fallback(
            parsed=parsed,
            transport_mode=transport_mode,
        )

    related_places, related_warnings = (
        _search_course_related_places(
            candidate_places=candidate_places,
            city=city,
            max_related_places=max(1, max_places // 3),
        )
    )
    related_places = _fill_missing_place_details(related_places)
    # 코스에서 붙는 연관 장소도 후보 군집(candidate_places)과 동떨어지지 않게 거리 필터를 통과시킨다
    related_places = _filter_places_within_radius(
        related_places,
        anchor_places=candidate_places,
    )

    # candidate_places/related_places는 취향 유사도 순위만으로 뽑혀서 음식점이 하나도
    # 안 섞여 있을 수 있다 — 점심/저녁 슬롯 수만큼 음식점 후보를 별도로 확보해서
    # _reorder_places_for_time_slots가 실제로 배정할 대상이 있게 한다.
    meal_slot_count = sum(1 for _, time_slot in time_slots if time_slot in MEAL_TIME_SLOTS)
    restaurant_places = _search_restaurant_places(
        city=city,
        anchor_places=candidate_places,
        max_restaurants=meal_slot_count,
        travel_style=travel_style,
        prefer_local=prefer_local,
    )

    candidate_count = max(
        1,
        max_places - len(related_places) - len(restaurant_places),
    )
    selected_places = _deduplicate_places(
        candidate_places[:candidate_count]
        + related_places
        + restaurant_places
    )[:max_places]
    selected_places = _reorder_places_for_time_slots(selected_places, time_slots)

    route_summary, route_warnings = _build_real_routes(
        selected_places=selected_places,
        transport_mode=transport_mode,
    )

    daily_schedule = _build_daily_schedule(
        selected_places=selected_places,
        routes=route_summary,
        travel_days=travel_days,
        schedule_intensity=schedule_intensity,
        travel_style=travel_style,
        season=season,
    )

    density_warnings = _check_daily_density(
        daily_schedule=daily_schedule,
        route_summary=route_summary,
        schedule_intensity=schedule_intensity,
    )

    if "겨울" in season:
        density_warnings.append(
            "겨울철은 일조시간이 짧아 저녁 시간대 일정을 제외했습니다."
        )

    # 1박 이상이면 숙박 후보를 명시적으로 하나 골라둔다 (RAG가 우연히 숙박을 관광지
    # 후보로 뽑아주길 기다리지 않고, Financial Agent가 실제 요금을 조회할 대상을 보장함)
    lodging_place = (
        _search_lodging_place(
            city=city,
            anchor_places=candidate_places,
            prefer_budget=prefer_budget,
            people_count=people_count,
            is_peak_season=is_peak_season,
            travel_style=travel_style,
        )
        if travel_days > 1
        else None
    )

    return {
        "tourist_spots": candidate_places,
        "candidate_places": candidate_places,
        "rag_ranked_places": rag_places,
        "related_places": related_places,
        "selected_places": selected_places,
        "route_summary": route_summary,
        "route_segments": route_summary,
        "daily_schedule": daily_schedule,
        "lodging_place": lodging_place,
        "season": season,
        "is_peak_season": is_peak_season,
        "warnings": related_warnings + route_warnings + density_warnings,
        "data_source": data_source,
    }