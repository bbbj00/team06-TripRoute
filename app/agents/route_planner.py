from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.services.kakao_mobility import get_route, summarize_route
from app.services.related_place_api import search_related_by_keyword
from app.services.tour_api import search_keyword
from app.tools.mock_tools import run_tool
from app.utils.transport_rules import estimate_public_transport_time


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
) -> List[Tuple[str, str]]:
    if "여유" in schedule_intensity:
        normal_slots = ["오전", "오후", "저녁"]
        last_day_slots = ["오전", "오후"]
    else:
        normal_slots = ["오전", "점심", "오후", "저녁"]
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


def _find_related_place_name(item: Dict[str, Any]) -> str | None:
    """
    related_place_api.py는 원본 item dict를 그대로 반환하므로,
    실제 응답에서 연관 관광지명 필드를 찾아 사용한다.
    """
    for key, value in item.items():
        normalized_key = key.lower().replace("_", "")

        if (
            isinstance(value, str)
            and value.strip()
            and "rlte" in normalized_key
            and ("nm" in normalized_key or "name" in normalized_key)
        ):
            return value.strip()

    return None


def _pick_matching_tour_item(
    items: List[Dict[str, Any]],
    target_name: str,
    area_code: str,
    signgu_code: str,
) -> Dict[str, Any] | None:
    if not items:
        return None

    target = re.sub(r"\s+", "", target_name).lower()

    def score(item: Dict[str, Any]) -> int:
        value = 0
        title = re.sub(
            r"\s+",
            "",
            str(item.get("title") or ""),
        ).lower()

        item_area = str(
            item.get("lDongRegnCd")
            or item.get("areacode")
            or ""
        )
        item_signgu = str(
            item.get("lDongSignguCd")
            or item.get("sigungucode")
            or ""
        )

        if title == target:
            value += 4
        elif target in title or title in target:
            value += 2

        if item_area == area_code:
            value += 1

        if item_signgu == signgu_code:
            value += 1

        return value

    return max(items, key=score)


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


def _search_real_related_places(
    candidate_places: List[Place],
    max_related_places: int,
) -> Tuple[List[Place], List[str]]:
    related_places: List[Place] = []
    warnings: List[str] = []

    for base_place in candidate_places[:3]:
        if len(related_places) >= max_related_places:
            break

        base_name = _get_place_name(base_place)
        area_code = str(base_place.get("area_code") or "")
        signgu_code = str(base_place.get("signgu_code") or "")

        if not area_code or not signgu_code:
            warnings.append(
                f"{base_name}: 지역 코드가 없어 연관 관광지 조회를 생략했습니다."
            )
            continue

        try:
            related_items = search_related_by_keyword(
                keyword=base_name,
                area_cd=area_code,
                signgu_cd=signgu_code,
                num_of_rows=10,
                page_no=1,
            )
        except Exception as exc:
            warnings.append(
                f"{base_name}: 연관 관광지 조회 실패 ({exc})"
            )
            continue

        for related_item in related_items:
            if len(related_places) >= max_related_places:
                break

            related_name = _find_related_place_name(related_item)
            if not related_name:
                continue

            try:
                tour_items = search_keyword(
                    keyword=related_name,
                    num_of_rows=5,
                    page_no=1,
                )
            except Exception as exc:
                warnings.append(
                    f"{related_name}: TourAPI 검색 실패 ({exc})"
                )
                continue

            matched = _pick_matching_tour_item(
                items=tour_items,
                target_name=related_name,
                area_code=area_code,
                signgu_code=signgu_code,
            )
            if not matched:
                continue

            related_places.append(
                _normalize_tour_place(
                    item=matched,
                    source="related_place_api",
                    reason=(
                        f"{base_name}과 함께 방문하기 좋은 "
                        "연관 관광지입니다."
                    ),
                )
            )

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
) -> List[Dict[str, Any]]:
    time_slots = _build_time_slots(
        travel_days=travel_days,
        schedule_intensity=schedule_intensity,
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
    time_slots = _build_time_slots(
        travel_days,
        schedule_intensity,
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
    schedule_intensity = str(
        parsed.get("schedule_intensity") or "보통"
    )

    travel_days = _parse_travel_days(duration)
    time_slots = _build_time_slots(
        travel_days,
        schedule_intensity,
    )
    max_places = len(time_slots)

    try:
        candidate_places = _search_real_places(
            city=city,
            max_places=max_places,
        )
    except Exception:
        return _build_mock_fallback(
            parsed=parsed,
            transport_mode=transport_mode,
        )

    if not candidate_places:
        return _build_mock_fallback(
            parsed=parsed,
            transport_mode=transport_mode,
        )

    related_places, related_warnings = (
        _search_real_related_places(
            candidate_places=candidate_places,
            max_related_places=max(1, max_places // 3),
        )
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
    )

    return {
        "tourist_spots": candidate_places,
        "candidate_places": candidate_places,
        "rag_ranked_places": [],
        "related_places": related_places,
        "selected_places": selected_places,
        "route_summary": route_summary,
        "route_segments": route_summary,
        "daily_schedule": daily_schedule,
        "warnings": related_warnings + route_warnings,
        "data_source": "real_api",
    }