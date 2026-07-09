from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.core.config import settings


def get_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)


def insert_place(
    content_id: str,
    title: str,
    overview: str,
    embedding: List[float],
    address: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """
    관광지 정보와 임베딩을 places 테이블에 저장합니다.
    content_id가 이미 있으면 덮어씁니다(upsert).
    """

    row = {
        "content_id": content_id,
        "title": title,
        "overview": overview,
        "address": address,
        "category": category,
        "embedding": embedding,
    }

    response = get_client().table("places").upsert(row, on_conflict="content_id").execute()
    return response.data


def get_places_missing_category(limit: int = 1000) -> List[Dict[str, Any]]:
    """
    category가 비어있는 관광지 행을 가져옵니다 (백필 대상 조회용).
    """

    response = (
        get_client()
        .table("places")
        .select("content_id")
        .is_("category", "null")
        .limit(limit)
        .execute()
    )
    return response.data


def update_place_category(content_id: str, category: str) -> Dict[str, Any]:
    """
    특정 content_id 행의 category만 갱신합니다.
    """

    response = (
        get_client()
        .table("places")
        .update({"category": category})
        .eq("content_id", content_id)
        .execute()
    )
    return response.data


def search_similar_places(query_embedding: List[float], match_count: int = 5) -> List[Dict[str, Any]]:
    """
    사용자 취향 임베딩과 가장 비슷한 관광지를 match_places RPC로 검색합니다.
    """

    response = get_client().rpc(
        "match_places",
        {"query_embedding": query_embedding, "match_count": match_count},
    ).execute()
    return response.data
