from typing import Any, Dict, List, Optional

from app.rag.embedder import embed_user_taste
from app.services.supabase_client import search_similar_places


def retrieve_places_by_taste(
    taste_text: str,
    match_count: int = 10,
    city: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    사용자 취향 문장과 의미적으로 가장 비슷한 관광지를 유사도 순으로 반환합니다.
    city를 넘기면 해당 도시의 관광지로 후보를 제한합니다.
    """

    query_embedding = embed_user_taste(taste_text)
    return search_similar_places(query_embedding, match_count=match_count, city=city)
