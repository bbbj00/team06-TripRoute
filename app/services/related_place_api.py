from typing import Any, Dict, List

import requests

from app.core.config import settings

BASE_URL = "https://apis.data.go.kr/B551011/TarRlteTarService1"

# 데이터 갱신주기가 매월 8일이라 최신 데이터가 없을 수 있는데,
# 테스트해보니 baseYm 값과 무관하게 최신 스냅샷을 그대로 반환함 (여러 달 값으로 확인).
DEFAULT_BASE_YM = "202504"


class RelatedPlaceAPIError(Exception):
    pass


def _request(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    query = {
        "serviceKey": settings.TOUR_API_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TripRoute",
        "_type": "json",
        **params,
    }

    response = requests.get(f"{BASE_URL}/{operation}", params=query, timeout=10)
    response.raise_for_status()
    body = response.json()

    header = body.get("response", {}).get("header") or body
    if header.get("resultCode") != "0000":
        raise RelatedPlaceAPIError(f"{operation} 실패: {header.get('resultCode')} {header.get('resultMsg')}")

    return body["response"]["body"]


def _extract_items(body: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = body.get("items", {}).get("item", [])
    return items if isinstance(items, list) else [items] if items else []


def get_related_by_area(
    area_cd: str,
    signgu_cd: str,
    base_ym: str = DEFAULT_BASE_YM,
    num_of_rows: int = 20,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    시군구(area_cd, signgu_cd) 기준으로 지역 내 관광지들의 연관 관광지 목록을 조회합니다.
    """

    params = {
        "baseYm": base_ym,
        "areaCd": area_cd,
        "signguCd": signgu_cd,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }

    body = _request("areaBasedList1", params)
    return _extract_items(body)


def search_related_by_keyword(
    keyword: str,
    area_cd: str,
    signgu_cd: str,
    base_ym: str = DEFAULT_BASE_YM,
    num_of_rows: int = 20,
    page_no: int = 1,
) -> List[Dict[str, Any]]:
    """
    관광지명(keyword)으로 검색해 그 관광지의 연관 관광지 목록을 조회합니다.
    area_cd/signgu_cd는 이 API 스펙상 여전히 필수 파라미터임.
    """

    params = {
        "baseYm": base_ym,
        "areaCd": area_cd,
        "signguCd": signgu_cd,
        "keyword": keyword,
        "numOfRows": num_of_rows,
        "pageNo": page_no,
    }

    body = _request("searchKeyword1", params)
    return _extract_items(body)
