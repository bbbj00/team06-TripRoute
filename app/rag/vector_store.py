import time
from typing import Any, Dict, List, Optional

from app.rag.embedder import embed_place_overviews
from app.services.supabase_client import (
    get_places_missing_category,
    insert_place,
    update_place_category,
)
from app.services.tour_api import TourAPIError, get_detail_common, search_keyword

# TourAPI contentTypeId 코드: 12=관광지, 14=문화시설, 15=축제공연행사,
# 25=여행코스, 28=레포츠, 32=숙박, 38=쇼핑, 39=음식점
DEFAULT_CONTENT_TYPE_IDS = ["12", "14", "15", "25", "28", "39"]

CONTENT_TYPE_ID_TO_CATEGORY = {
    "12": "관광지",
    "14": "문화시설",
    "15": "축제공연행사",
    "25": "여행코스",
    "28": "레포츠",
    "32": "숙박",
    "38": "쇼핑",
    "39": "음식점",
}


def content_type_id_to_category(content_type_id: Optional[str]) -> Optional[str]:
    return CONTENT_TYPE_ID_TO_CATEGORY.get(content_type_id)


def ingest_city(
    city: str,
    num_of_rows: int = 30,
    content_type_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    TourAPI에서 도시 기준으로 관광지를 검색하고, 개요를 임베딩해 Supabase places 테이블에 저장합니다.
    content_type_ids를 넘기면 카테고리별로 각각 num_of_rows만큼 검색해서 합칩니다
    (안 넘기면 DEFAULT_CONTENT_TYPE_IDS 기준으로 관광지/문화시설/축제/여행코스/레포츠/음식점을 다 조회).
    overview가 없는 항목은 건너뛰고, 이미 저장된 content_id는 upsert로 덮어씁니다.
    """

    type_ids = content_type_ids if content_type_ids is not None else DEFAULT_CONTENT_TYPE_IDS

    candidates = []
    seen_content_ids = set()
    for type_id in type_ids:
        try:
            results = search_keyword(city, content_type_id=type_id, num_of_rows=num_of_rows)
        except TourAPIError as e:
            print(f"  [경고] {city}/{type_id} 검색 실패, 건너뜀: {e}")
            continue
        for candidate in results:
            if candidate["contentid"] in seen_content_ids:
                continue
            seen_content_ids.add(candidate["contentid"])
            candidates.append(candidate)

    print(f"  {city}: 검색 결과 {len(candidates)}건, 상세정보 조회 중...")

    details = []
    for candidate in candidates:
        try:
            detail = get_detail_common(candidate["contentid"])
        except TourAPIError as e:
            print(f"  [경고] {city}/{candidate['contentid']} 상세조회 실패, 건너뜀: {e}")
            continue
        overview = (detail.get("overview") or "").strip()
        if not overview:
            continue
        detail["overview"] = overview
        details.append(detail)

    if not details:
        return []

    # Upstage 임베딩 API는 한 번에 너무 많은 입력을 보내면 실패할 수 있어 배치로 나눠서 호출
    BATCH_SIZE = 50
    saved = []
    for i in range(0, len(details), BATCH_SIZE):
        batch = details[i : i + BATCH_SIZE]
        embeddings = embed_place_overviews([d["overview"] for d in batch])

        for detail, embedding in zip(batch, embeddings):
            insert_place(
                content_id=detail["contentid"],
                title=detail.get("title", ""),
                overview=detail["overview"],
                embedding=embedding,
                address=detail.get("addr1"),
                category=content_type_id_to_category(detail.get("contenttypeid")),
            )
            saved.append({"title": detail.get("title"), "content_id": detail["contentid"]})

    return saved


def backfill_categories() -> Dict[str, int]:
    """
    category가 비어있는 기존 places 행들에 대해 TourAPI를 다시 조회해서 category를 채워넣습니다.
    """

    targets = get_places_missing_category(limit=5000)
    print(f"카테고리 백필 대상: {len(targets)}건")

    updated = 0
    failed = 0
    for i, row in enumerate(targets):
        content_id = row["content_id"]
        try:
            detail = get_detail_common(content_id)
        except TourAPIError as e:
            print(f"  [경고] {content_id} 상세조회 실패: {e}")
            failed += 1
            time.sleep(1)  # rate limit(429) 대비, 실패 시 조금 더 쉬어감
            continue

        category = content_type_id_to_category(detail.get("contenttypeid"))
        if not category:
            failed += 1
            continue

        time.sleep(0.2)  # TourAPI rate limit 방지용 호출 간 딜레이
        if (i + 1) % 100 == 0:
            print(f"  진행: {i + 1}/{len(targets)}")

        update_place_category(content_id, category)
        updated += 1

    print(f"백필 완료: {updated}건 갱신, {failed}건 실패")
    return {"updated": updated, "failed": failed}


def ingest_cities(
    cities: List[str],
    num_of_rows: int = 30,
    content_type_ids: Optional[List[str]] = None,
) -> Dict[str, int]:
    """
    여러 도시를 순서대로 ingest_city()에 넘겨 일괄 수집합니다.
    """

    result = {}
    for city in cities:
        print(f"[{city}] 수집 시작")
        try:
            saved = ingest_city(city, num_of_rows=num_of_rows, content_type_ids=content_type_ids)
            result[city] = len(saved)
            print(f"[{city}] 완료: {len(saved)}건 저장")
        except Exception as e:
            print(f"[{city}] 실패, 다음 도시로 넘어감: {type(e).__name__}: {e}")
            result[city] = 0
    return result
