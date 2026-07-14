from typing import Any, Dict, List, Optional

from app.rag.embedder import embed_user_taste
from app.services.supabase_client import search_similar_places

# match_places는 city_filter로 좁힌 코퍼스 안에서 코사인 거리 기준 top-N을 그대로
# 반환한다 — 도시 전체가 취향과 무관한 테마로만 채워져 있어도 match_count만큼 무관한
# 장소가 그대로 반환된다는 뜻이다. similarity가 이 값 미만이면 "취향과 무관"으로 보고
# 걸러내서, 진짜 관련 있는 곳이 없을 때는 빈 리스트를 반환해 호출자가 TourAPI 실시간
# 검색으로 넘어갈 수 있게 한다.
MIN_SIMILARITY = 0.5


def retrieve_places_by_taste(
    taste_text: str,
    match_count: int = 10,
    city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    사용자 취향 문장과 의미적으로 가장 비슷한 관광지를 유사도 순으로 반환합니다.
    city를 넘기면 해당 도시의 관광지로 후보를 제한합니다. similarity가 MIN_SIMILARITY
    미만인 결과는 취향과 무관하다고 보고 제외합니다.
    """

    query_embedding = embed_user_taste(taste_text)
    results = search_similar_places(query_embedding, match_count=match_count, city=city)
    return [
        item for item in results
        if item.get("similarity") is None or item.get("similarity") >= MIN_SIMILARITY
    ]
