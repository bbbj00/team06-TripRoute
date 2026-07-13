# ui/gradio_app.py

from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr


# ---------------------------------------------------------
# 프로젝트 루트를 Python 경로에 추가
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.agents.react_loop import run_triproute_react_loop  # noqa: E402
from app.utils.formatter import (  # noqa: E402
    format_condition_summary,
    format_cost_summary,
    format_daily_schedule,
    format_react_trace,
    format_route_summary,
    format_warnings,
)


# ---------------------------------------------------------
# 기본값
# ---------------------------------------------------------
DEFAULT_MESSAGE = (
    "강릉으로 1박 2일 여행 가고 싶어. "
    "바다랑 감성 카페, 먹거리를 좋아해."
)

WELCOME_MESSAGE = """
안녕하세요! **TripRoute AI 여행 플래너**입니다.

아래처럼 여행 조건을 자연어로 입력해주세요.

> 강릉으로 1박 2일 여행 가고 싶어.
> 바다랑 감성 카페, 먹거리를 좋아해.

여행 계획이 완성되면 아래 **결과 패널**에서 일정 · 동선 · 비용을 확인할 수 있어요.
"""

LOADING_MESSAGE = "여행 계획을 만들고 있어요..."

RESULT_PLACEHOLDER = (
    "아직 생성된 여행 계획이 없습니다.\n\n"
    "왼쪽에서 여행 요청을 입력하고 **여행 계획 생성**을 눌러주세요."
)

PARSER_LABELS = {
    "solar": "Solar API",
    "mock": "Mock fallback",
}


# ---------------------------------------------------------
# 결과 패널 렌더링
# ---------------------------------------------------------
def _build_result_sections(result: dict):
    return (
        format_daily_schedule(result),
        format_route_summary(result),
        format_cost_summary(result),
        format_condition_summary(result),
        format_warnings(result),
        format_react_trace(result),
    )


NO_RESULT_UPDATE = (
    gr.update(),
    gr.update(),
    gr.update(),
    gr.update(),
    gr.update(),
    gr.update(),
)


# ---------------------------------------------------------
# 챗봇 메시지 처리 (제너레이터: 로딩 상태 → 최종 결과)
# ---------------------------------------------------------
def chat(
    message: str,
    history: list[dict[str, str]] | None,
    transport_mode: str,
    people_count: int | float,
):
    if history is None:
        history = []

    normalized_message = (message or "").strip()

    if not normalized_message:
        yield (history, "", *NO_RESULT_UPDATE)
        return

    history = history + [{"role": "user", "content": normalized_message}]

    # 1) 로딩 상태를 먼저 보여준다
    loading_history = history + [
        {"role": "assistant", "content": LOADING_MESSAGE}
    ]
    yield (loading_history, "", *NO_RESULT_UPDATE)

    # 2) 실제 계획 생성
    try:
        normalized_people_count = int(people_count)

        result = run_triproute_react_loop(
            user_input=normalized_message,
            transport_mode=transport_mode,
            people_count=normalized_people_count,
        )

        result_sections = _build_result_sections(result)

        parser = result.get("condition_summary", {}).get("parser", "unknown")
        parser_name = PARSER_LABELS.get(parser, parser)

        reply = (
            "여행 계획을 생성했어요.\n\n"
            f"- 입력 분석: **{parser_name}**\n"
            f"- 이동수단: **{transport_mode}**\n"
            f"- 여행 인원: **{normalized_people_count}명**\n\n"
            "아래 **결과 패널**에서 일정 · 동선 · 비용을 확인해주세요."
        )

        final_history = history + [{"role": "assistant", "content": reply}]

        yield (final_history, "", *result_sections)

    except ValueError as error:
        error_reply = f"여행 조건을 확인해주세요.\n\n- 원인: `{error}`"
        final_history = history + [{"role": "assistant", "content": error_reply}]
        yield (final_history, "", *NO_RESULT_UPDATE)

    except Exception as error:
        error_reply = (
            "여행 계획을 생성하는 중 오류가 발생했습니다.\n\n"
            f"- 오류 종류: `{type(error).__name__}`\n"
            f"- 오류 내용: `{error}`"
        )
        final_history = history + [{"role": "assistant", "content": error_reply}]
        yield (final_history, "", *NO_RESULT_UPDATE)


# ---------------------------------------------------------
# 대화 초기화
# ---------------------------------------------------------
def clear_chat():
    return (
        [],
        "",
        RESULT_PLACEHOLDER,
        RESULT_PLACEHOLDER,
        RESULT_PLACEHOLDER,
        RESULT_PLACEHOLDER,
        RESULT_PLACEHOLDER,
        RESULT_PLACEHOLDER,
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

    /* Gradio 내장 컴포넌트(라디오/슬라이더/탭 밑줄 등) 포인트 컬러 오버라이드.
       --color-accent은 Gradio 테마 전역 포인트 컬러라, 이걸 안 바꾸면 탭 선택
       밑줄 등 일부 내장 컴포넌트가 기본 테마 오렌지색으로 그대로 남는다. */
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

/* 시스템이 다크모드여도 이 앱은 항상 라이트 톤으로 고정한다.
   Gradio는 OS가 다크모드면 루트에 .dark 클래스를 붙이고 자체 다크 테마 변수
   (--background-fill-primary 등)를 쓰는데, 위 :root 오버라이드만으로는 특정
   클래스(챗봇/입력창/버튼 등)에 안 붙어 있어서 검정 배경+흰 글씨가 그대로 남았다.
   :root와 .dark 양쪽에 동일한 라이트 값을 강제해서 다크모드 여부와 무관하게
   항상 같은 톤이 나오게 한다. */
.gradio-container,
.gradio-container * {
    color-scheme: light !important;
}

:root,
.dark {
    --background-fill-primary: #FFFFFF !important;
    --body-background-fill: var(--tr-outer-bg) !important;
    --block-background-fill: var(--tr-card-bg) !important;
    --input-background-fill: #FFFFFF !important;
    --body-text-color: var(--tr-text) !important;
    --border-color-primary: var(--tr-border) !important;
}

/* 라디오/슬라이더/체크박스 선택 색이 브라우저 기본(오렌지 계열)으로 남지 않도록
   특정 컴포넌트 클래스가 아니라 네이티브 accent-color로 전역 지정한다. */
input[type="radio"],
input[type="range"],
input[type="checkbox"] {
    accent-color: var(--tr-primary) !important;
}

body {
    background: var(--tr-outer-bg) !important;
}

.gradio-container {
    max-width: 1440px !important;
    margin: 40px auto !important;
    background: var(--tr-card-bg) !important;
    border-radius: 24px !important;
    box-shadow: 0 20px 60px rgba(40, 50, 110, 0.15);
    font-family: "Pretendard", "Inter", -apple-system, sans-serif;
    padding: 8px 32px 32px !important;
}

#title-box {
    text-align: center;
    margin-bottom: 4px;
}

#title-box h1 {
    color: var(--tr-text);
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 4px;
}

#title-box p {
    color: var(--tr-text-muted);
}

/* 사이드바 (여행 설정) */
.sidebar {
    background: var(--tr-card-bg) !important;
    border: 1px solid var(--tr-border) !important;
    border-radius: 16px !important;
    padding: 24px !important;
}

#new-chat-button {
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 999px !important;
    font-weight: 700;
    min-height: 44px;
}
#new-chat-button:hover {
    background: var(--tr-primary-hover) !important;
}

#chatbot {
    min-height: 420px;
    background: var(--tr-card-bg) !important;
}

/* 유저/AI 발화 모두 카드 없이, 아래 구분선만 */
#chatbot .message-row {
    border-bottom: 1px solid var(--tr-border);
}
#chatbot .panel.user-row,
#chatbot .panel.bot-row {
    background: transparent !important;
}

/* 결과 패널: 표마다 카드로 구분 */
#result-panel table {
    background: var(--tr-table-bg);
    border: 1px solid var(--tr-border);
    border-radius: 16px;
    border-collapse: separate;
    border-spacing: 0;
    overflow: hidden;
    width: 100%;
}
#result-panel th {
    background: var(--tr-table-header-bg);
    color: #4A4A55;
    padding: 8px 12px;
    text-align: left;
}
#result-panel td {
    padding: 8px 12px;
    border-top: 1px solid var(--tr-border);
}

#message-input textarea {
    border-radius: 28px !important;
    border: 1px solid var(--tr-border) !important;
    box-shadow: 0 8px 24px rgba(40, 50, 110, 0.08);
}
#message-input textarea:focus {
    border-color: var(--tr-primary) !important;
}

#send-button {
    min-height: 44px;
    min-width: 44px;
    font-weight: 700;
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 999px !important;
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
<script>
(function () {
  var url = new URL(window.location.href);
  if (url.searchParams.get("__theme") !== "light") {
    url.searchParams.set("__theme", "light");
    window.location.replace(url.toString());
  }
})();
</script>
<link rel="stylesheet" as="style" crossorigin
  href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
"""


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------
with gr.Blocks(
    title="TripRoute AI 여행 플래너",
) as demo:

    gr.Markdown(
        """
# TripRoute AI 여행 플래너

Solar API와 Agentic Workflow를 활용한 국내 여행 일정 생성 챗봇
""",
        elem_id="title-box",
    )

    with gr.Row():

        # 왼쪽 사이드바 (여행 설정)
        with gr.Column(
            scale=1,
            min_width=250,
            elem_classes=["sidebar"],
        ):
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
                label="TripRoute AI",
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
                lines=3,
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
            with gr.Tab("주의사항"):
                warnings_out = gr.Markdown(RESULT_PLACEHOLDER)
            with gr.Tab("실행 과정 (디버그)"):
                trace_out = gr.Markdown(RESULT_PLACEHOLDER)

    gr.Markdown(
        """
> 현재 여행지와 이동정보 일부는 MVP용 Mock 데이터를 사용하며,
> 입력 조건 분석은 Solar API 또는 Mock fallback으로 처리됩니다.
"""
    )

    # -----------------------------------------------------
    # 이벤트 연결
    # -----------------------------------------------------
    chat_outputs = [
        chatbot,
        message_input,
        schedule_out,
        route_out,
        cost_out,
        condition_out,
        warnings_out,
        trace_out,
    ]

    send_button.click(
        fn=chat,
        inputs=[
            message_input,
            chatbot,
            transport_mode,
            people_count,
        ],
        outputs=chat_outputs,
        show_progress="minimal",
    )

    message_input.submit(
        fn=chat,
        inputs=[
            message_input,
            chatbot,
            transport_mode,
            people_count,
        ],
        outputs=chat_outputs,
        show_progress="minimal",
    )

    clear_button.click(
        fn=clear_chat,
        inputs=[],
        outputs=chat_outputs,
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
