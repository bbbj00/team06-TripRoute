# ui/gradio_app.py

from __future__ import annotations

import html
import sys
import time
from pathlib import Path

import gradio as gr


# ---------------------------------------------------------
# 프로젝트 루트를 Python 경로에 추가
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.agents.react_loop import stream_triproute_react_loop  # noqa: E402
from app.services import auth_client, chat_store  # noqa: E402
from app.services.upstage_client import stream_trip_summary  # noqa: E402
from app.utils.formatter import (  # noqa: E402
    format_condition_summary,
    format_cost_summary,
    format_daily_schedule,
    format_route_summary,
)


# ---------------------------------------------------------
# 기본값
# ---------------------------------------------------------
DEFAULT_MESSAGE = (
    "강릉으로 1박 2일 여행 가고 싶어. "
    "바다랑 감성 카페, 먹거리를 좋아해."
)

WELCOME_MESSAGE = (
    "안녕하세요! <b>TripRoute AI 여행 플래너</b>입니다.<br><br>"
    "아래처럼 여행 조건을 자연어로 입력해주세요.<br><br>"
    "<span style='color:#8B8D98;'>&gt; 강릉으로 1박 2일 여행 가고 싶어.<br>"
    "&gt; 바다랑 감성 카페, 먹거리를 좋아해.</span><br><br>"
    "여행 계획이 완성되면 아래 <b>결과 패널</b>에서 일정 · 동선 · 비용을 확인할 수 있어요.<br>"
    "로그인하면 대화 기록이 저장되고, \"카페 말고 맛집 위주로 바꿔줘\" 같은 후속 요청도<br>"
    "이전 조건을 이어받아 처리됩니다."
)

LOADING_MESSAGE = "여행 계획을 만들고 있어요..."

RESULT_PLACEHOLDER = (
    "아직 생성된 여행 계획이 없습니다.\n\n"
    "왼쪽에서 여행 요청을 입력하고 **여행 계획 생성**을 눌러주세요."
)

LOGIN_ERROR_MESSAGE = "이메일 또는 비밀번호를 확인해주세요."
SIGNUP_PENDING_MESSAGE = (
    "가입 처리 중 문제가 발생했습니다. 이미 가입된 이메일이면 로그인해주세요."
)
EMPTY_AUTH_INPUT_MESSAGE = "이메일과 비밀번호를 입력해주세요."

# access_token 만료 이 시간(초) 전부터는 미리 refresh_token으로 갱신한다
TOKEN_REFRESH_MARGIN_SECONDS = 60

GUEST_BROWSER_STATE = {"refresh_token": None, "user_id": None, "email": None}


# ---------------------------------------------------------
# 결과 패널 렌더링
# ---------------------------------------------------------
def _build_result_sections(result: dict):
    return (
        format_daily_schedule(result),
        format_route_summary(result),
        format_cost_summary(result),
        format_condition_summary(result),
    )


NO_RESULT_UPDATE = (
    gr.update(),
    gr.update(),
    gr.update(),
    gr.update(),
)

RESET_RESULT_TUPLE = (
    RESULT_PLACEHOLDER,
    RESULT_PLACEHOLDER,
    RESULT_PLACEHOLDER,
    RESULT_PLACEHOLDER,
)


# ---------------------------------------------------------
# 로그인 상태 갱신/조회 헬퍼
# ---------------------------------------------------------
def _ensure_fresh_access_token(access_token_info, auth_state):
    """
    로그인 상태면 access_token 만료가 임박했는지 확인하고, 필요하면 refresh_token으로
    미리 갱신한다. Supabase는 refresh_token을 1회용으로 회전시키므로 새로 받은
    refresh_token을 auth_state(BrowserState)에도 같이 반영해야 다음 갱신이 안 깨진다.
    갱신에 실패하면 로그인이 만료된 것으로 보고 조용히 게스트 상태로 되돌린다.

    반환값: (access_token_info, auth_state, is_logged_in)
    """
    if not access_token_info or not access_token_info.get("access_token"):
        return None, auth_state, False

    if time.time() < access_token_info.get("expires_at", 0) - TOKEN_REFRESH_MARGIN_SECONDS:
        return access_token_info, auth_state, True

    refresh_token = (auth_state or {}).get("refresh_token")
    if not refresh_token:
        return None, dict(GUEST_BROWSER_STATE), False

    session = auth_client.refresh_session(refresh_token)
    if session is None or not session.get("access_token"):
        return None, dict(GUEST_BROWSER_STATE), False

    new_access_token_info = {
        "access_token": session["access_token"],
        "expires_at": time.time() + (session.get("expires_in") or 3600),
        "user_id": session["user_id"],
    }
    new_auth_state = {
        "refresh_token": session["refresh_token"],
        "user_id": session["user_id"],
        "email": session["email"],
    }
    return new_access_token_info, new_auth_state, True


def _session_label(session: dict) -> str:
    title = session.get("title")
    if title:
        return title

    summary = session.get("last_condition_summary") or {}
    city = summary.get("city")
    if city:
        return f"{city} 여행"

    return "새 대화"


def _session_choices(sessions):
    return [(_session_label(session), session["id"]) for session in sessions]


def _guest_ui_updates():
    return (
        gr.update(visible=True),   # logged_out_group
        gr.update(visible=False),  # logged_in_group
        "",                        # welcome_text
        gr.update(choices=[], value=None, visible=False),  # session_radio
        gr.update(visible=False),  # no_session_msg
        None,                      # access_token_state
        dict(GUEST_BROWSER_STATE),  # auth_browser_state
        [],                        # recent_sessions_state
        gr.update(visible=True),   # login_trigger_btn
    )


def _logged_in_ui_updates(email, access_token, expires_at, user_id, sessions, refresh_token):
    has_sessions = len(sessions) > 0
    return (
        gr.update(visible=False),  # logged_out_group
        gr.update(visible=True),   # logged_in_group
        f"<div style='text-align:center; font-size:16px; font-weight:bold; color:#0052cc; margin-bottom:16px;'>{email}님 환영합니다</div>",  # welcome_text
        gr.update(choices=_session_choices(sessions), value=None, visible=has_sessions),  # session_radio
        gr.update(visible=not has_sessions),  # no_session_msg
        {"access_token": access_token, "expires_at": expires_at, "user_id": user_id},
        {"refresh_token": refresh_token, "user_id": user_id, "email": email},
        sessions,
        gr.update(visible=False),  # login_trigger_btn — 로그인하면 사이드바에 최근 대화가 바로 보이니 필요 없음
    )


def restore_login(auth_state):
    """페이지 로드 시 BrowserState의 refresh_token으로 로그인 상태를 복구한다."""
    refresh_token = (auth_state or {}).get("refresh_token")

    if not refresh_token:
        return (*_guest_ui_updates(), "")

    session = auth_client.refresh_session(refresh_token)

    if session is None or not session.get("access_token"):
        return (*_guest_ui_updates(), "")

    expires_at = time.time() + (session.get("expires_in") or 3600)

    try:
        sessions = chat_store.list_recent_sessions(session["user_id"])
    except Exception:
        sessions = []

    return (
        *_logged_in_ui_updates(
            email=session["email"],
            access_token=session["access_token"],
            expires_at=expires_at,
            user_id=session["user_id"],
            sessions=sessions,
            refresh_token=session["refresh_token"],
        ),
        "",
    )


def do_signup(email: str, password: str):
    email = (email or "").strip()
    password = password or ""

    if not email or not password:
        return (*_guest_ui_updates(), EMPTY_AUTH_INPUT_MESSAGE)

    try:
        session = auth_client.sign_up(email, password)
    except auth_client.AuthError as error:
        return (*_guest_ui_updates(), f"회원가입 실패: {error}")

    if not session.get("access_token"):
        return (*_guest_ui_updates(), SIGNUP_PENDING_MESSAGE)

    expires_at = time.time() + (session.get("expires_in") or 3600)

    try:
        sessions = chat_store.list_recent_sessions(session["user_id"])
    except Exception:
        sessions = []

    return (
        *_logged_in_ui_updates(
            email=session["email"],
            access_token=session["access_token"],
            expires_at=expires_at,
            user_id=session["user_id"],
            sessions=sessions,
            refresh_token=session["refresh_token"],
        ),
        "",
    )


def do_login(email: str, password: str):
    email = (email or "").strip()
    password = password or ""

    if not email or not password:
        return (*_guest_ui_updates(), EMPTY_AUTH_INPUT_MESSAGE)

    try:
        session = auth_client.sign_in(email, password)
    except auth_client.AuthError:
        return (*_guest_ui_updates(), LOGIN_ERROR_MESSAGE)

    if not session.get("access_token"):
        return (*_guest_ui_updates(), LOGIN_ERROR_MESSAGE)

    expires_at = time.time() + (session.get("expires_in") or 3600)

    try:
        sessions = chat_store.list_recent_sessions(session["user_id"])
    except Exception:
        sessions = []

    return (
        *_logged_in_ui_updates(
            email=session["email"],
            access_token=session["access_token"],
            expires_at=expires_at,
            user_id=session["user_id"],
            sessions=sessions,
            refresh_token=session["refresh_token"],
        ),
        "",
    )


def do_logout(access_token_info, auth_state):
    access_token = (access_token_info or {}).get("access_token")
    refresh_token = (auth_state or {}).get("refresh_token")

    if access_token and refresh_token:
        try:
            auth_client.sign_out(access_token, refresh_token)
        except auth_client.AuthError:
            pass

    return (
        *_guest_ui_updates(),
        "",
        [{"role": "assistant", "content": WELCOME_MESSAGE}],
        "",
        None,
        None,
        "",
    )


def load_session(session_id, auth_browser_state):
    """
    사이드바 '최근 대화' 목록에서 세션을 선택하면 그 대화 기록을 불러온다.

    access_token_state/recent_sessions_state를 입력으로 받는 대신 auth_browser_state
    (user_id 포함)만으로 직접 조회한다 — do_login/do_signup처럼 실제 네트워크 I/O가 있는
    이벤트가 access_token_state/recent_sessions_state를 gr.BrowserState와 같은 출력
    배치에서 갱신하면, 이후 다른 이벤트(session_radio.change)에는 이 State들이 None으로
    넘어오는 문제가 있었다(원인을 좁혀봤지만 Gradio 6.20 자체의 동작으로 보이고 더 깊이
    파진 못했다). auth_browser_state는 이 문제 없이 항상 정상적으로 넘어와서 이걸로 대체.
    """
    user_id = (auth_browser_state or {}).get("user_id")

    if not session_id or not user_id:
        return (gr.update(),) * 5 + RESET_RESULT_TUPLE

    try:
        messages = chat_store.get_session_messages(session_id, user_id)
    except Exception:
        messages = []

    history = [
        {"role": message["role"], "content": message["content"]}
        for message in messages
    ]
    if not history:
        history = [{"role": "assistant", "content": WELCOME_MESSAGE}]

    try:
        sessions = chat_store.list_recent_sessions(user_id)
    except Exception:
        sessions = []

    session_row = next(
        (s for s in sessions if s.get("id") == session_id),
        None,
    )
    previous_condition = (session_row or {}).get("last_condition_summary")

    try:
        stored_result = chat_store.get_session_result(session_id, user_id)
    except Exception:
        stored_result = None

    result_sections = (
        _build_result_sections(stored_result) if stored_result else RESET_RESULT_TUPLE
    )

    return (history, "", previous_condition, stored_result, session_id, *result_sections)


# ---------------------------------------------------------
# 챗봇 메시지 처리 (제너레이터: 로딩 상태 → 최종 결과)
# ---------------------------------------------------------
def chat(
    message: str,
    history: list[dict[str, str]] | None,
    transport_mode: str,
    people_count: int | float,
    access_token_info,
    previous_condition,
    previous_result,
    active_session_id,
    auth_state,
):
    if history is None:
        history = []

    normalized_message = (message or "").strip()

    # "새 대화" 버튼(clear_chat)이 메시지를 보내기 전에 이미 제목 없는 세션을 미리
    # 만들어두므로, session_id의 신규 여부만으로는 "이 세션의 첫 메시지인지"를 알 수
    # 없다 — 화면에 표시된 이전 대화 중 사용자 메시지가 하나도 없으면 첫 메시지로 본다.
    is_first_message_in_session = not any(
        turn.get("role") == "user" for turn in history
    )

    # 사이드바 "최근 대화" 갱신 정보(session_radio, recent_sessions_state, no_session_msg) —
    # 새 세션이 생기거나 제목이 바뀌기 전까지는 그대로 두고(gr.update()), 실제로 목록이
    # 바뀌는 시점에만 새로 계산해서 덮어쓴다.
    sidebar_update = (gr.update(), gr.update(), gr.update())

    if not normalized_message:
        yield (
            history, "", *NO_RESULT_UPDATE,
            previous_condition, previous_result, active_session_id,
            access_token_info, auth_state, *sidebar_update,
        )
        return

    access_token_info, auth_state, is_logged_in = _ensure_fresh_access_token(
        access_token_info, auth_state
    )

    history = history + [{"role": "user", "content": normalized_message}]

    # 1) 스트리밍이 시작되기 전(첫 Solar 호출 전)에도 즉시 뭔가 보이도록 초기 로딩 상태를
    # 먼저 보여준다. 이후엔 단계별 진행 메시지(아래 for 루프)가 이 자리를 계속 갱신한다.
    loading_history = history + [
        {"role": "assistant", "content": LOADING_MESSAGE}
    ]
    yield (
        loading_history, "", *NO_RESULT_UPDATE,
        previous_condition, previous_result, active_session_id,
        access_token_info, auth_state, *sidebar_update,
    )

    session_id = active_session_id

    if is_logged_in:
        try:
            if session_id is None:
                session_row = chat_store.create_session(
                    access_token_info["user_id"],
                    title=normalized_message[:40],
                )
                session_id = session_row["id"]
                # 대화를 만들자마자(첫 응답이 나오기 한참 전이라도) 사이드바 "최근 대화"
                # 목록에 바로 보이도록 여기서 즉시 갱신한다 — 끝까지 기다렸다가 갱신하면
                # 생성 직후엔 목록에 안 보이는 문제가 있었음.
                sessions = chat_store.list_recent_sessions(access_token_info["user_id"])
                sidebar_update = (
                    gr.update(choices=_session_choices(sessions), visible=True),
                    sessions,
                    gr.update(visible=False),
                )
            chat_store.append_message(session_id, "user", normalized_message)
        except Exception:
            pass

    # 2) 실제 계획 생성 — 노드가 끝날 때마다 진행 메시지를 받아 채팅 버블을 갱신한다.
    try:
        normalized_people_count = int(people_count)
        result = None

        for progress_message, maybe_result in stream_triproute_react_loop(
            user_input=normalized_message,
            transport_mode=transport_mode,
            people_count=normalized_people_count,
            previous_condition_summary=previous_condition,
            previous_result=previous_result,
            # 로그인 세션의 session_id를 그대로 체크포인트 thread_id로 재사용해서,
            # 같은 대화는 LangGraph 체크포인터에도 같은 단위로 쌓이게 한다.
            thread_id=session_id,
        ):
            progress_history = history + [
                {"role": "assistant", "content": progress_message}
            ]
            yield (
                progress_history, "", *NO_RESULT_UPDATE,
                previous_condition, previous_result, active_session_id,
                access_token_info, auth_state, *sidebar_update,
            )
            if maybe_result is not None:
                result = maybe_result

        result_sections = _build_result_sections(result)
        new_condition = result.get("condition_summary")

        city = new_condition.get("city", "알 수 없는 지역") if new_condition else "알 수 없는 지역"
        themes = new_condition.get("travel_style", []) if new_condition else []
        theme_str = ", ".join(themes) if themes else "일반"
        duration = new_condition.get("duration", "알 수 없는 기간") if new_condition else "알 수 없는 기간"

        header = (
            "요청하신 여행 계획 생성이 완료되었습니다! ✨<br><br>"
            f"✅ <b>장소:</b> {city}<br>"
            f"✅ <b>기간:</b> {duration}<br>"
            f"✅ <b>인원:</b> {normalized_people_count}명<br>"
            f"✅ <b>이동수단:</b> {transport_mode}<br>"
            f"✅ <b>테마:</b> {theme_str}<br><br>"
        )

        # 3) 자연어 설명 문단만 Solar stream=True로 타이핑 효과를 내며 이어붙인다.
        # daily_schedule/cost_summary 같은 계산된 수치 데이터는 이미 위에서 확정된
        # result_sections로 한 번에 표시되고, 스트리밍 대상이 아니다.
        #
        # output 가드레일: chatbot 말풍선은 HTML로 그대로 렌더링되므로(header가 이미
        # <b>/<br> 태그를 raw HTML로 씀), 사용자 입력 문구가 Solar 응답에 일부라도
        # 그대로 echo되면 XSS로 이어질 수 있다. streamed_text(LLM이 생성한 부분)만
        # html.escape()로 이스케이프하고, 우리가 직접 쓰는 고정 문구(header, 아래
        # 실패 시 fallback 문구)의 의도된 태그는 그대로 유지한다.
        streamed_text = ""
        used_fallback_reason = False
        try:
            for delta in stream_trip_summary(
                new_condition, result["daily_schedule"], result["cost_summary"]
            ):
                streamed_text += delta
                partial_history = history + [
                    {"role": "assistant", "content": header + html.escape(streamed_text)}
                ]
                yield (
                    partial_history, "", *result_sections,
                    new_condition, result, session_id,
                    access_token_info, auth_state, *sidebar_update,
                )
        except Exception:
            # 설명 문장 생성 실패는 계획 자체의 실패가 아니므로, 고정 문구로 대체하고
            # 계속 진행한다(결과 패널은 이미 정상적으로 채워져 있음).
            used_fallback_reason = True
            streamed_text = (
                "위 조건으로 일정, 동선, 비용을 최적화했습니다. "
                "아래 <b>결과 패널</b>에서 상세 내용을 확인해 주세요!"
            )

        reply = header + (
            streamed_text if used_fallback_reason else html.escape(streamed_text)
        )
        final_history = history + [{"role": "assistant", "content": reply}]

        if is_logged_in and session_id is not None:
            try:
                chat_store.append_message(session_id, "assistant", reply)
                chat_store.update_session_condition_summary(session_id, new_condition)
                # 결과 패널(일정/동선/비용)도 통째로 저장해둔다 — "최근 대화"에서 이
                # 세션을 다시 열었을 때 대화 내용뿐 아니라 그때 만든 일정도 같이 복원됨.
                chat_store.update_session_result(session_id, result)
                if is_first_message_in_session:
                    # 첫 메시지 그대로 자르는 대신(또는 "새 대화" 버튼으로 미리 만들어져
                    # 제목이 아예 없는 세션이든) 도시·기간으로 요약된 제목을 붙인다 —
                    # "최근 대화" 목록에서 어떤 여행인지 한눈에 알 수 있게.
                    chat_store.update_session_title(session_id, f"{city} {duration} 여행")
                    # 사이드바에 이미 임시 제목(또는 "새 대화")으로 보이던 항목을
                    # 최종 제목으로 다시 갱신한다.
                    sessions = chat_store.list_recent_sessions(access_token_info["user_id"])
                    sidebar_update = (
                        gr.update(choices=_session_choices(sessions), visible=True),
                        sessions,
                        gr.update(visible=False),
                    )
            except Exception:
                pass

        yield (
            final_history, "", *result_sections,
            new_condition, result, session_id,
            access_token_info, auth_state, *sidebar_update,
        )

    except ValueError as error:
        error_reply = f"여행 조건을 확인해주세요.\n\n- 원인: `{error}`"
        final_history = history + [{"role": "assistant", "content": error_reply}]
        yield (
            final_history, "", *NO_RESULT_UPDATE,
            previous_condition, previous_result, session_id,
            access_token_info, auth_state, *sidebar_update,
        )

    except Exception as error:
        error_reply = (
            "여행 계획을 생성하는 중 오류가 발생했습니다.\n\n"
            f"- 오류 종류: `{type(error).__name__}`\n"
            f"- 오류 내용: `{error}`"
        )
        final_history = history + [{"role": "assistant", "content": error_reply}]
        yield (
            final_history, "", *NO_RESULT_UPDATE,
            previous_condition, previous_result, session_id,
            access_token_info, auth_state, *sidebar_update,
        )


# ---------------------------------------------------------
# 대화 초기화
# ---------------------------------------------------------
def clear_chat(access_token_info):
    is_logged_in = bool(access_token_info and access_token_info.get("access_token"))
    new_session_id = None
    sidebar_update = (gr.update(), gr.update(), gr.update())

    if is_logged_in:
        try:
            session_row = chat_store.create_session(access_token_info["user_id"])
            new_session_id = session_row["id"]
            # 여기서 만든 세션은 아직 제목/메시지가 없어 "새 대화"로만 보이지만(첫
            # 메시지를 보내면 chat()에서 도시·기간 제목으로 갱신됨), 최소한 사이드바
            # 목록에는 클릭 즉시 나타나야 한다.
            sessions = chat_store.list_recent_sessions(access_token_info["user_id"])
            sidebar_update = (
                gr.update(choices=_session_choices(sessions), visible=True),
                sessions,
                gr.update(visible=False),
            )
        except Exception:
            new_session_id = None

    return (
        [],
        "",
        *RESET_RESULT_TUPLE,
        None,
        None,
        new_session_id,
        *sidebar_update,
    )


# ---------------------------------------------------------
# "CHAT A.I+" 스타일 CSS (docs/ui_claude_design_spec.md 기준)
# ---------------------------------------------------------
CUSTOM_CSS = """
:root {
    --tr-outer-bg: #C9D6F2;
    --tr-card-bg: #FFFFFF;
    --tr-primary: #6C63FF;
    --tr-primary-hover: #5A52E0;
    --tr-text: #1A1A1A;
    --tr-text-muted: #8B8D98;
    --tr-border: #EDEDF2;
    --tr-selected-bg: #EEF0FC;
    --tr-pill-bg: #F3F3F8;
    --tr-table-bg: #FAFAFC;
    --tr-table-header-bg: #F1F1FA;

    --color-accent: var(--tr-primary);
    --color-accent-soft: var(--tr-selected-bg);
    --checkbox-background-color-selected: var(--tr-primary);
    --checkbox-background-color-selected-dark: var(--tr-primary);
    --checkbox-border-color-selected: var(--tr-primary);
    --checkbox-label-background-fill-selected: var(--tr-primary);
    --slider-color: var(--tr-primary);
    --button-primary-background-fill: var(--tr-primary);
    --button-primary-background-fill-hover: var(--tr-primary-hover);
}

.gradio-container,
.gradio-container * {
    color-scheme: light !important;
}

:root,
.dark,
.gradio-container {
    --background-fill-primary: #FFFFFF !important;
    --background-fill-secondary: #FFFFFF !important;
    --body-background-fill: var(--tr-outer-bg) !important;
    --block-background-fill: var(--tr-card-bg) !important;
    --input-background-fill: #FFFFFF !important;
    --body-text-color: var(--tr-text) !important;
    --border-color-primary: var(--tr-border) !important;
    --slider-color: var(--tr-primary) !important;
    --slider-color-hover: var(--tr-primary) !important;
    --color-accent: var(--tr-primary) !important;
}

.dark .message-wrap,
.dark .message-row,
.dark .message,
.dark .panel {
    background-color: transparent !important;
}

#login-trigger-btn {
    background: #fff !important;
    border: 1px solid var(--tr-border) !important;
    color: var(--tr-text) !important;
    border-radius: 999px !important;
    min-height: 44px;
    font-weight: 600;
}
#login-trigger-btn:hover {
    background: var(--tr-selected-bg) !important;
}

/* Fix Login Input boxes and labels in dark mode */
.dark input[type="text"], 
.dark input[type="password"] {
    background-color: #fff !important;
    color: var(--tr-text) !important;
    border: 1px solid var(--tr-border) !important;
}

/* Fix faint block-info labels without making everything thick */
span[data-testid="block-info"] {
    color: var(--tr-text) !important;
    opacity: 1 !important;
}

#auth-overlay {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    background: rgba(0, 0, 0, 0.4) !important;
    z-index: 99998 !important;
    backdrop-filter: blur(4px);
    margin: 0 !important;
    padding: 0 !important;
}
#auth-modal {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 99999 !important;
    width: 400px !important;
    max-width: 90vw !important;
    min-height: 400px !important;
    background: #fff !important;
    box-shadow: 0 20px 60px rgba(0,0,0,0.2) !important;
    border-radius: 24px !important;
    padding: 32px !important;
    margin: 0 !important;
    box-sizing: border-box !important;
    overflow: visible !important;
}
#auth-modal > * {
    overflow: visible !important;
}
#close-modal-btn {
    position: absolute !important;
    top: 16px !important;
    right: 16px !important;
    width: 32px !important;
    height: 32px !important;
    min-width: 32px !important;
    min-height: 32px !important;
    border-radius: 50% !important;
    background: #f1f1f1 !important;
    border: none !important;
    color: #000 !important;
    font-size: 16px !important;
    font-weight: bold !important;
    padding: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 999999 !important;
    cursor: pointer !important;
}
#close-modal-btn:hover {
    background: #e2e2e2 !important;
}
#auth-modal.hide, #auth-modal.hidden, #auth-modal.svelte-1gfkn6j.hide {
    display: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
#auth-overlay.hide, #auth-overlay.hidden, #auth-overlay.svelte-1gfkn6j.hide {
    display: none !important;
    opacity: 0 !important;
    pointer-events: none !important;
}
#auth-modal h3 {
    margin: 0 0 20px 0 !important;
    font-size: 20px !important;
    text-align: center !important;
    color: var(--tr-text) !important;
}
#auth-modal .prose {
    background: transparent !important;
}
#login-btn {
    background: #6C63FF !important;
    color: #fff !important;
    border: none !important;
}
#login-btn:hover {
    background: #5A52D5 !important;
}
#signup-btn {
    background: #f1f5f9 !important;
    color: #334155 !important;
    border: none !important;
}
#signup-btn:hover {
    background: #e2e8f0 !important;
}
#auth-message {
    color: #6C63FF !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    text-align: center !important;
    margin-top: 12px !important;
}
/* 로그인 후 사이드바에 바로 뜨는 최근 대화 블록 — 아래 "여행 설정"과 구분되게 여백/구분선 추가 */
#logged-in-group {
    margin-bottom: 20px !important;
    padding-bottom: 20px !important;
    border-bottom: 1px solid var(--tr-border) !important;
}
#welcome-text {
    font-size: 16px !important;
    font-weight: 600 !important;
    color: var(--tr-text) !important;
    margin-bottom: 20px !important;
    text-align: center !important;
    padding: 10px !important;
}
#welcome-text .prose {
    background: transparent !important;
}
#logout-btn {
    background: #f1f5f9 !important;
    color: #ef4444 !important;
    border: none !important;
    font-weight: bold !important;
    margin-bottom: 16px !important;
}
#logout-btn:hover {
    background: #fee2e2 !important;
}
#recent-session-title {
    margin-top: 24px !important;
    margin-bottom: 12px !important;
    font-size: 14px !important;
    font-weight: bold !important;
    color: var(--tr-text-light) !important;
    text-align: center !important;
}
#recent-session-title .prose {
    background: transparent !important;
}

/* "이동수단" 라디오: 체크박스 대신 세그먼트 pill 그룹으로 변경 */
#transport-mode .wrap {
    display: flex !important;
    flex-wrap: wrap;
    gap: 8px;
    background: transparent !important;
    border: none !important;
}
#transport-mode label {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    border: 1px solid var(--tr-border) !important;
    background: var(--tr-pill-bg) !important;
    border-radius: 999px !important;
    padding: 8px 14px !important;
    font-size: 13px;
    color: #4A4A55;
    text-align: center;
}
#transport-mode label input {
    display: none !important;
}
#transport-mode label.selected {
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-color: var(--tr-primary) !important;
    font-weight: 600;
}

/* 로그인/회원가입 카드 내부 텍스트 인풋 스타일 오버라이드 (팝업) */
#logged-out-group input,
#logged-in-group input {
    border-radius: 12px !important;
    border: 1px solid var(--tr-border) !important;
    background: #fff !important;
    padding: 10px 14px !important;
    font-size: 13px !important;
    color: var(--tr-text) !important;
}

input[type="range"],
input[type="checkbox"] {
    accent-color: var(--tr-primary) !important;
}

#session-radio .wrap {
    display: flex !important;
    flex-direction: column;
    gap: 2px;
    background: transparent !important;
    border: none !important;
}
#session-radio label {
    border: none !important;
    background: transparent !important;
    border-radius: 12px !important;
    padding: 10px 12px !important;
    font-size: 14px;
    color: #4A4A55;
    justify-content: flex-start !important;
}
#session-radio label input {
    display: none !important;
}
#session-radio label.selected {
    background: var(--tr-selected-bg) !important;
    color: var(--tr-primary) !important;
    font-weight: 700;
}

body {
    background: var(--tr-outer-bg) !important;
}

.gradio-container {
    max-width: 1680px !important;
    width: 96vw !important;
    margin: 40px auto !important;
    background: var(--tr-card-bg) !important;
    border-radius: 24px !important;
    box-shadow: 0 20px 60px rgba(40, 50, 110, 0.15);
    font-family: "Pretendard", "Inter", -apple-system, sans-serif;
    padding: 8px 40px 40px !important;
}

#title-box {
    text-align: center;
    margin-bottom: 24px;
    padding-top: 16px;
}

#title-box h1 {
    color: var(--tr-text);
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin: 0 0 4px 0;
    font-size: 26px;
}

#title-box p {
    color: var(--tr-text-muted);
    margin: 0;
    font-size: 14px;
}

.sidebar {
    background: var(--tr-card-bg) !important;
    border: 1px solid var(--tr-border) !important;
    border-radius: 16px !important;
    padding: 24px !important;
    gap: 24px !important;
}

#new-chat-button {
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 999px !important;
    font-weight: 700;
    min-height: 44px;
    font-size: 14px;
    padding: 12px;
}
#new-chat-button:hover {
    background: var(--tr-primary-hover) !important;
}

#chatbot {
    min-height: 420px;
    background: #FFFFFF !important;
    background-color: #FFFFFF !important;
    border: 1px solid var(--tr-border) !important;
    border-radius: 16px !important;
    padding: 20px !important;
    box-sizing: border-box;
}

/* 유저 발화: 인디고 톤 말풍선 버블 + 폰트 동기화 */
#chatbot .message.user {
    background: var(--tr-selected-bg) !important;
    border: none !important;
    border-radius: 20px 20px 4px 20px !important;
    color: var(--tr-text) !important;
    padding: 14px 18px !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    max-width: 70% !important;
    font-family: "Pretendard", "Inter", -apple-system, sans-serif !important;
    word-break: break-word !important;
}
/* Gradio가 메시지 마크다운을 렌더링할 때 <p> 뒤에 항상 줄바꿈 문자를 하나 더 붙여서,
   pre-wrap이면 유저 말풍선(배경색 있는 버블)에서 그 여백이 그대로 보인다(봇 답변은
   배경이 투명해서 안 보였을 뿐). 문단 구분은 마크다운의 <p> 태그가 이미 담당하므로
   pre-wrap 없이도 여러 줄 입력이 깨지지 않는다.
*/
#chatbot .message.user p:last-child {
    margin-bottom: 0 !important;
}

#chatbot .message.bot {
    background: transparent !important;
    border: none !important;
    padding: 14px 4px !important;
    color: var(--tr-text) !important;
    font-size: 15px !important;
    line-height: 1.7 !important;
    font-family: "Pretendard", "Inter", -apple-system, sans-serif !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}

#result-panel .tab-nav {
    border-bottom: 1px solid var(--tr-border) !important;
    margin-bottom: 16px !important;
    display: flex !important;
    gap: 4px !important;
    background: transparent !important;
}
#result-panel .tab-nav button {
    padding: 10px 16px !important;
    font-size: 14px !important;
    color: var(--tr-text-muted) !important;
    border: none !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
    border-radius: 0 !important;
    font-weight: normal !important;
    cursor: pointer;
}
#result-panel .tab-nav button:hover {
    color: var(--tr-primary) !important;
    background: transparent !important;
}
#result-panel .tab-nav button.selected {
    color: var(--tr-primary) !important;
    border-bottom-color: var(--tr-primary) !important;
    font-weight: 700 !important;
}

#result-panel-title h3 {
    font-weight: 700;
    color: var(--tr-text);
    margin: 28px 0 12px;
    font-size: 16px;
}

#result-panel {
    border: 1px solid var(--tr-border) !important;
    border-radius: 16px !important;
    padding: 20px !important;
}

#result-panel table {
    background: var(--tr-table-bg);
    border: 1px solid var(--tr-border);
    border-radius: 16px;
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    width: 100%;
    font-size: 14px;
    margin-bottom: 20px;
}
#result-panel th {
    background: var(--tr-table-header-bg) !important;
    color: #4A4A55 !important;
    padding: 10px 14px !important;
    text-align: left;
    border: none !important;
    font-weight: normal;
}
#result-panel td {
    padding: 10px 14px !important;
    border: none !important;
    border-top: 1px solid var(--tr-border) !important;
    color: var(--tr-text) !important;
}
#result-panel tr:first-child td {
    border-top: none !important;
}
#result-panel h3 {
    color: var(--tr-primary) !important;
    font-size: 15px !important;
    margin: 20px 0 8px !important;
    font-weight: 700 !important;
}

#message-input textarea {
    border-radius: 28px !important;
    border: 1px solid var(--tr-border) !important;
    box-shadow: 0 8px 24px rgba(40, 50, 110, 0.08) !important;
    padding: 16px 20px !important;
    font-size: 14px !important;
    color: var(--tr-text) !important;
    font-family: "Pretendard", "Inter", -apple-system, sans-serif !important;
    white-space: pre-wrap !important;
}
#message-input textarea:focus {
    border-color: var(--tr-primary) !important;
}

#send-button {
    min-height: 48px;
    font-weight: 700;
    font-size: 14px;
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 999px !important;
    padding: 12px 24px !important;
    align-self: flex-start !important;
}
#send-button:hover {
    background: var(--tr-primary-hover) !important;
}
"""

# Pretendard 웹폰트 실제 로딩 (CUSTOM_CSS의 font-family 지정만으로는 로드되지 않음) +
# 시스템 다크모드여도 항상 라이트로 강제.
#
# Gradio는 `<head data-gradio-mode>window.__gradio_mode__ = "app";</script>`를 정적 HTML에
# 동기 스크립트로 직접 박아두고, `head=`로 넘긴 커스텀 스크립트는 클라이언트가 /config를
# 받아온 "뒤에" 동적으로 주입한다 — 이미 Gradio 프론트엔드가 다크/라이트를 판단하는 시점(앱
# 마운트 시)보다 늦게 실행돼서 window.__gradio_mode__를 여기서 바꿔봐야 소용없다(직접 확인:
# Playwright로 다크모드 에뮬레이션 후 body에 "dark" 클래스가 계속 남아있는 것으로 검증).
# 반면 URL 쿼리 파라미터 `?__theme=light`는 Gradio가 테마를 판단하는 바로 그 시점에
# window.location에서 즉시 읽으므로 타이밍 문제가 없다(Playwright로 확인 완료). 그래서
# 최초 진입 시 이 파라미터가 없으면 붙여서 한 번 리다이렉트시키는 방식으로 강제한다.
HEAD_HTML = """
<link rel="stylesheet" as="style" crossorigin
  href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
"""


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------
with gr.Blocks(
    title="TripRoute AI 여행 플래너",
) as demo:

    # 로그인 지속용: 브라우저 localStorage에 refresh_token/user_id/email만 저장한다.
    # access_token은 절대 여기 저장하지 않는다(서버 State에만 둠) — 백엔드가 service_role
    # 키만 쓰고 RLS를 안 타므로 access_token은 "누가 로그인했는지 증명"하는 용도 그 이상이
    # 아니고, 굳이 브라우저에 남길 필요가 없다.
    auth_browser_state = gr.BrowserState(dict(GUEST_BROWSER_STATE))
    access_token_state = gr.State(None)
    previous_condition_state = gr.State(None)
    # 직전 턴의 전체 결과(daily_schedule/route_summary 포함) — 기간 연장 후속 요청에서
    # 기존 일정을 유지한 채 늘어난 날짜만 새로 채우는 데 쓴다(previous_condition_state와
    # 항상 같이 갱신됨).
    previous_result_state = gr.State(None)
    active_session_id_state = gr.State(None)
    recent_sessions_state = gr.State([])

    gr.Markdown(
        """
# TripRoute AI 여행 플래너

Solar API와 Agentic Workflow를 활용한 국내 여행 일정 생성 챗봇
""",
        elem_id="title-box",
    )

    with gr.Group(visible=False, elem_id="auth-overlay") as auth_overlay:
        pass

    with gr.Group(visible=False, elem_id="auth-modal") as auth_modal:
        close_modal_btn = gr.Button("✕", elem_id="close-modal-btn")

        with gr.Group(visible=True, elem_id="logged-out-group") as logged_out_group:
            gr.Markdown("### 로그인 / 회원가입")
            email_input = gr.Textbox(label="이메일")
            password_input = gr.Textbox(label="비밀번호", type="password")
            with gr.Row():
                login_button = gr.Button("로그인", variant="primary", elem_id="login-btn")
                signup_button = gr.Button("회원가입", variant="secondary", elem_id="signup-btn")
            auth_message = gr.Markdown("", elem_id="auth-message")

    with gr.Row():

        # 왼쪽 사이드바 (여행 설정)
        with gr.Column(
            scale=1,
            min_width=250,
            elem_classes=["sidebar"],
        ):
            login_trigger_btn = gr.Button("👤 로그인 / 내 정보", elem_id="login-trigger-btn")

            # 로그인하면 이 모달 밖 사이드바에 바로 최근 대화 목록을 보여준다 —
            # "로그인/내정보" 버튼을 다시 눌러 모달을 열어야 최근 대화가 보이던
            # 기존 방식은 사용자가 못 찾는 문제가 있었음.
            with gr.Group(visible=False, elem_id="logged-in-group") as logged_in_group:
                welcome_text = gr.Markdown("", elem_id="welcome-text")
                logout_button = gr.Button("로그아웃", variant="secondary", elem_id="logout-btn")
                gr.Markdown("### 최근 대화", elem_id="recent-session-title")
                session_radio = gr.Radio(
                    choices=[],
                    label="",
                    show_label=False,
                    elem_id="session-radio",
                )
                no_session_msg = gr.Markdown("최근 대화 내역이 없습니다.", elem_id="no-session-msg", visible=False)

            gr.Markdown("### 여행 설정")

            transport_mode = gr.Radio(
                choices=[
                    "대중교통",
                    "택시",
                    "자차",
                    "렌터카",
                ],
                value="대중교통",
                label="이동수단",
                elem_id="transport-mode",
            )

            people_count = gr.Slider(
                minimum=1,
                maximum=10,
                step=1,
                value=2,
                label="여행 인원",
            )

            clear_button = gr.Button(
                "새 대화 시작",
                variant="secondary",
                elem_id="new-chat-button",
            )

            gr.Markdown(
                """
### 입력 예시

- 강릉으로 1박 2일 여행 가고 싶어.
- 전주에서 한옥과 맛집 중심으로 여행하고 싶어.
- 부산으로 2박 3일 렌터카 여행을 계획해줘.

대중교통 시간과 비용은 참고용 추정치입니다.
"""
            )

        # 오른쪽 챗봇 영역
        with gr.Column(
            scale=3,
            min_width=600,
        ):
            chatbot = gr.Chatbot(
                show_label=False,
                height=420,
                elem_id="chatbot",
                value=[{"role": "assistant", "content": WELCOME_MESSAGE}],
                buttons=["copy"],
                feedback_options=("Like", "Dislike"),
            )

            message_input = gr.Textbox(
                label="여행 요청",
                placeholder=(
                    "여행 지역, 기간, 취향을 입력해주세요. "
                    "예) " + DEFAULT_MESSAGE
                ),
                lines=1,
                max_lines=5,
                elem_id="message-input",
            )

            send_button = gr.Button(
                "여행 계획 생성",
                variant="primary",
                elem_id="send-button",
            )

    gr.Markdown("### 결과 패널", elem_id="result-panel-title")

    with gr.Column(elem_id="result-panel"):
        with gr.Tabs():
            with gr.Tab("일정표"):
                schedule_out = gr.Markdown(RESULT_PLACEHOLDER)
            with gr.Tab("이동 동선"):
                route_out = gr.Markdown(RESULT_PLACEHOLDER)
            with gr.Tab("예상 비용"):
                cost_out = gr.Markdown(RESULT_PLACEHOLDER)
            with gr.Tab("조건 요약"):
                condition_out = gr.Markdown(RESULT_PLACEHOLDER)

    gr.Markdown(
        """
> 현재 여행지와 이동정보 일부는 MVP용 Mock 데이터를 사용하며,
> 입력 조건 분석은 Solar API 또는 Mock fallback으로 처리됩니다.
"""
    )

    # -----------------------------------------------------
    # 이벤트 연결
    # -----------------------------------------------------
    result_tab_outputs = [
        schedule_out,
        route_out,
        cost_out,
        condition_out,
    ]

    chat_outputs = [
        chatbot,
        message_input,
        *result_tab_outputs,
        previous_condition_state,
        previous_result_state,
        active_session_id_state,
        access_token_state,
        auth_browser_state,
        session_radio,
        recent_sessions_state,
        no_session_msg,
    ]

    chat_inputs = [
        message_input,
        chatbot,
        transport_mode,
        people_count,
        access_token_state,
        previous_condition_state,
        previous_result_state,
        active_session_id_state,
        auth_browser_state,
    ]

    send_button.click(
        fn=chat,
        inputs=chat_inputs,
        outputs=chat_outputs,
        show_progress="minimal",
    )

    message_input.submit(
        fn=chat,
        inputs=chat_inputs,
        outputs=chat_outputs,
        show_progress="minimal",
    )

    clear_chat_outputs = [
        chatbot,
        message_input,
        *result_tab_outputs,
        previous_condition_state,
        previous_result_state,
        active_session_id_state,
        session_radio,
        recent_sessions_state,
        no_session_msg,
    ]

    clear_button.click(
        fn=clear_chat,
        inputs=[access_token_state],
        outputs=clear_chat_outputs,
    )

    auth_outputs = [
        logged_out_group,
        logged_in_group,
        welcome_text,
        session_radio,
        no_session_msg,
        access_token_state,
        auth_browser_state,
        recent_sessions_state,
        login_trigger_btn,
        auth_message,
    ]

    def open_modal():
        return gr.update(visible=True), gr.update(visible=True)

    def close_modal():
        return gr.update(visible=False), gr.update(visible=False)

    # Gradio의 Group visible=False 토글은 실제로 DOM을 닫지 않고(내부적으로
    # 크기만 접으려고 시도), #auth-modal/#auth-overlay에 걸어둔 커스텀 CSS의
    # !important 크기 지정(min-height, position:fixed 등)이 그 축소를 그대로
    # 덮어써서 빈 박스가 화면에 계속 남는다. 그래서 실제 open/close는 JS로
    # "hide" 클래스를 직접 토글해서 처리한다(CSS에 이미 정의된 .hide 규칙 사용).
    OPEN_MODAL_JS = """
    () => {
        document.getElementById('auth-overlay')?.classList.remove('hide');
        document.getElementById('auth-modal')?.classList.remove('hide');
    }
    """

    CLOSE_MODAL_JS = """
    () => {
        document.getElementById('auth-overlay')?.classList.add('hide');
        document.getElementById('auth-modal')?.classList.add('hide');
    }
    """

    # 로그인/회원가입 성공 시에만 모달을 닫는다(실패 시엔 에러 메시지를 보여줘야
    # 하므로 열어둬야 함) — logged-in-group이 실제로 렌더링되었는지로 성공 여부를 판단.
    CLOSE_MODAL_ON_AUTH_SUCCESS_JS = """
    () => {
        const loggedIn = document.getElementById('logged-in-group');
        if (loggedIn && loggedIn.getBoundingClientRect().height > 0) {
            document.getElementById('auth-overlay')?.classList.add('hide');
            document.getElementById('auth-modal')?.classList.add('hide');
        }
    }
    """

    login_trigger_btn.click(
        fn=open_modal,
        inputs=[],
        outputs=[auth_overlay, auth_modal],
    ).then(fn=None, js=OPEN_MODAL_JS)

    close_modal_btn.click(
        fn=close_modal,
        inputs=[],
        outputs=[auth_overlay, auth_modal],
    ).then(fn=None, js=CLOSE_MODAL_JS)

    demo.load(
        fn=restore_login,
        inputs=[auth_browser_state],
        outputs=auth_outputs,
    )

    login_button.click(
        fn=do_login,
        inputs=[email_input, password_input],
        outputs=auth_outputs,
    ).then(fn=None, js=CLOSE_MODAL_ON_AUTH_SUCCESS_JS)

    signup_button.click(
        fn=do_signup,
        inputs=[email_input, password_input],
        outputs=auth_outputs,
    ).then(fn=None, js=CLOSE_MODAL_ON_AUTH_SUCCESS_JS)

    logout_button.click(
        fn=do_logout,
        inputs=[access_token_state, auth_browser_state],
        outputs=[
            *auth_outputs,
            chatbot,
            message_input,
            previous_condition_state,
            previous_result_state,
            active_session_id_state,
        ],
    )

    session_radio.change(
        fn=load_session,
        inputs=[session_radio, auth_browser_state],
        outputs=[
            chatbot,
            message_input,
            previous_condition_state,
            previous_result_state,
            active_session_id_state,
            *result_tab_outputs,
        ],
    )


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------
if __name__ == "__main__":
    demo.queue()

    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
        theme=gr.themes.Default(),
        css=CUSTOM_CSS,
        head=HEAD_HTML,
    )
