from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Tuple

from app.rag.retriever import retrieve_places_by_taste
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
from app.utils.transport_rules import estimate_public_transport_time

COURSE_CONTENT_TYPE_ID = "25"
# 코스 하위 장소는 "몇 일차"인지 구분이 없어서, 매칭된 장소 기준 코스 내 순서(subnum)로
# 이 범위 안에 있는 것만 연관 장소로 추천함 (며칠짜리 코스든 상관없이 먼 구간이 섞이는 것 방지)
COURSE_NEARBY_WINDOW = 2

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


def _normalize_tour_place(
    item: Dict[str, Any],
    source: str,
    reason: str,
) -> Place:
    """
    TourAPI searchKeyword2 결과를 Route Planner 내부 형식으로 변환한다.
    """
    title = str(item.get("title") or "장소명 없음").strip()

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
        "reason": reason,
        "source": source,
        "raw": item,
    }


def _build_taste_text(travel_style: List[str], prefer_local: bool) -> str:
    style_text = ", ".join(travel_style) if travel_style else "여행"

    if prefer_local:
        return f"{style_text}을(를) 좋아하고, 사람이 많이 몰리지 않는 로컬 분위기의 장소"

    return f"{style_text}을(를) 좋아하는 여행"


def _normalize_rag_place(item: Dict[str, Any], reason: str) -> Place:
    """
    match_places RPC 결과(Supabase places 테이블 행)를 Route Planner 내부 형식으로 변환한다.

    Supabase places 테이블에는 좌표(위도/경도)가 없어서 longitude/latitude는 일단 None으로
    두고, 이후 _fill_missing_place_details()에서 TourAPI로 보완한다.
    """
    title = str(item.get("title") or "장소명 없음").strip()

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
        "reason": reason,
        "source": "rag",
        "rating": item.get("rating"),
        "review_count": item.get("review_count"),
        "category": item.get("category"),
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

    reason = (
        f"{', '.join(travel_style)} 취향과 RAG 유사도가 높은 {city} 지역 관광지입니다."
        if travel_style
        else f"{city} 지역의 관광지 후보입니다."
    )

    places = _deduplicate_places(
        [_normalize_rag_place(item, reason) for item in results]
    )

    return _sort_by_prefer_local(places, prefer_local)


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
    # 겨울은 일조시간이 짧아 저녁 시간대 야외 일정이 부담스러우므로 저녁 슬롯을 아예 뺀다.
    # (계절이 몇 시에 해가 지는지까지 정밀 반영하긴 어려우니, "저녁 슬롯 유무"라는 단순한
    # 방식으로 근사함 — 봄/여름/가을은 기존과 동일)
    is_short_daylight_season = "겨울" in season

    if "여유" in schedule_intensity:
        normal_slots = ["오전", "오후"] if is_short_daylight_season else ["오전", "오후", "저녁"]
        last_day_slots = ["오전", "오후"]
    else:
        normal_slots = (
            ["오전", "점심", "오후"]
            if is_short_daylight_season
            else ["오전", "점심", "오후", "저녁"]
        )
        last_day_slots = ["오전", "점심", "오후"]

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
                reason=f"{city} 지역의 관광지 후보입니다.",
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
    del people_count

    city = str(parsed.get("city") or "강릉")
    duration = str(parsed.get("duration") or "1박 2일")
    travel_style = list(parsed.get("travel_style") or [])
    prefer_local = bool(parsed.get("prefer_local", False))
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

    candidate_count = max(
        1,
        max_places - len(related_places),
    )
    selected_places = _deduplicate_places(
        candidate_places[:candidate_count]
        + related_places
    )[:max_places]

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

    return {
        "tourist_spots": candidate_places,
        "candidate_places": candidate_places,
        "rag_ranked_places": rag_places,
        "related_places": related_places,
        "selected_places": selected_places,
        "route_summary": route_summary,
        "route_segments": route_summary,
        "daily_schedule": daily_schedule,
        "warnings": related_warnings + route_warnings + density_warnings,
        "data_source": data_source,
    }