from typing import Any, Dict, Optional

import requests

from app.core.config import settings

BASE_URL = "https://maps.googleapis.com/maps/api/place"


class GooglePlacesAPIError(Exception):
    pass


def find_place(name: str, address: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    장소 이름(+주소)으로 Google Places를 검색해서 가장 유력한 후보 1건을 가져옵니다.
    TourAPI에는 place_id가 없어서 이름+주소 텍스트 검색으로 매칭하며, 동명 장소가 있으면
    엉뚱한 곳이 매칭될 수 있습니다. 일치하는 곳이 없으면 None을 반환합니다.
    """

    query = f"{name} {address}" if address else name
    params = {
        "input": query,
        "inputtype": "textquery",
        "fields": "place_id,name,rating,user_ratings_total,formatted_address",
        "key": settings.GOOGLE_PLACES_API_KEY,
    }

    response = requests.get(f"{BASE_URL}/findplacefromtext/json", params=params, timeout=10)
    response.raise_for_status()
    body = response.json()

    status = body.get("status")
    if status == "ZERO_RESULTS":
        return None
    if status != "OK":
        raise GooglePlacesAPIError(f"findplacefromtext 실패: {status} {body.get('error_message')}")

    candidates = body.get("candidates", [])
    return candidates[0] if candidates else None


def get_rating_and_review_count(name: str, address: Optional[str] = None) -> Dict[str, Optional[Any]]:
    """
    장소의 평점(rating)과 리뷰 수(review_count)만 뽑아서 반환합니다.
    매칭 실패 시 둘 다 None입니다.
    """

    place = find_place(name, address)
    if not place:
        return {"rating": None, "review_count": None}

    return {
        "rating": place.get("rating"),
        "review_count": place.get("user_ratings_total"),
    }
