# app/services/chat_store.py
#
# 로그인한 사용자의 대화 세션/메시지를 Supabase(chat_sessions/chat_messages)에
# 저장·조회한다. 테이블 DDL은 docs/sql/chat_history.sql 참고.
#
# 백엔드는 Supabase service_role 키로 접속해 RLS를 우회하므로, "이 세션이 정말
# 이 user_id 소유인가"는 여기서 직접 확인해야 한다 — 그렇지 않으면 조작되거나
# 잘못된 session_id로 다른 사용자의 대화를 읽을 수 있다.

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.supabase_client import get_service_client as get_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(user_id: str, title: Optional[str] = None) -> Dict[str, Any]:
    """새 대화 세션을 만든다."""
    row = {"user_id": user_id, "title": title}
    response = get_client().table("chat_sessions").insert(row).execute()
    return response.data[0]


def list_recent_sessions(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """로그인한 사용자의 최근 대화 목록을 최신순으로 가져온다."""
    response = (
        get_client()
        .table("chat_sessions")
        .select("id, title, last_condition_summary, created_at, updated_at")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data


def _session_belongs_to_user(session_id: str, user_id: str) -> bool:
    response = (
        get_client()
        .table("chat_sessions")
        .select("id")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return bool(response.data)


def get_session_messages(session_id: str, user_id: str) -> List[Dict[str, Any]]:
    """
    세션의 메시지를 시간순으로 가져온다. session_id가 실제로 user_id 소유가
    아니면 빈 목록을 반환한다.
    """
    if not _session_belongs_to_user(session_id, user_id):
        return []

    response = (
        get_client()
        .table("chat_messages")
        .select("id, role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return response.data


def append_message(session_id: str, role: str, content: str) -> Dict[str, Any]:
    """세션에 메시지를 하나 추가하고, 세션의 updated_at도 같이 갱신한다."""
    row = {"session_id": session_id, "role": role, "content": content}
    response = get_client().table("chat_messages").insert(row).execute()

    get_client().table("chat_sessions").update(
        {"updated_at": _now_iso()}
    ).eq("id", session_id).execute()

    return response.data[0]


def update_session_condition_summary(
    session_id: str,
    condition_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    세션에 마지막 condition_summary를 저장한다 — 나중에 이 세션을 다시 열었을 때
    맥락 이어가기(previous_condition_summary)의 출발점이 된다.
    """
    response = (
        get_client()
        .table("chat_sessions")
        .update(
            {
                "last_condition_summary": condition_summary,
                "updated_at": _now_iso(),
            }
        )
        .eq("id", session_id)
        .execute()
    )
    return response.data[0]


def update_session_title(session_id: str, title: str) -> Dict[str, Any]:
    """세션 제목을 갱신한다(보통 첫 사용자 메시지를 잘라서 제목으로 씀)."""
    response = (
        get_client()
        .table("chat_sessions")
        .update({"title": title})
        .eq("id", session_id)
        .execute()
    )
    return response.data[0]
