from typing import Any, Dict, Tuple

import requests

from app.core.config import settings

BASE_URL = "https://apis-navi.kakaomobility.com/v1/directions"


class KakaoMobilityError(Exception):
    pass


def get_route(
    origin: Tuple[float, float],
    destination: Tuple[float, float],
    priority: str = "RECOMMEND",
) -> Dict[str, Any]:
    """
    두 좌표 간 자동차 기준 경로를 조회합니다.

    origin/destination은 (경도, 위도) 순서의 튜플입니다.
    (TourAPI의 mapx=경도, mapy=위도와 순서가 같음)
    """

    headers = {"Authorization": f"KakaoAK {settings.KAKAO_MOBILITY_API_KEY}"}
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{destination[0]},{destination[1]}",
        "priority": priority,
    }

    response = requests.get(BASE_URL, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    body = response.json()

    routes = body.get("routes", [])
    if not routes or routes[0].get("result_code") != 0:
        route = routes[0] if routes else {}
        raise KakaoMobilityError(f"길찾기 실패: {route.get('result_code')} {route.get('result_msg')}")

    return routes[0]


def summarize_route(route: Dict[str, Any]) -> Dict[str, Any]:
    """
    get_route()의 결과에서 동선 계산에 필요한 값만 추려냅니다.
    """

    summary = route["summary"]
    return {
        "distance_km": round(summary["distance"] / 1000, 1),
        "duration_min": round(summary["duration"] / 60),
        "taxi_fare": summary["fare"]["taxi"],
        "toll_fare": summary["fare"]["toll"],
    }
