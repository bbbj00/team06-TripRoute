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
# Claude.ai 스타일 CSS (docs/ui_claude_design_spec.md 기준)
# ---------------------------------------------------------
CUSTOM_CSS = """
:root {
    --tr-bg: #F5F4ED;
    --tr-surface: #FAFAF7;
    --tr-primary: #C4633F;
    --tr-primary-hover: #B0532F;
    --tr-text: #3D3929;
    --tr-text-muted: #6B6A62;
    --tr-border: #D8D5C9;
    --tr-bubble-user: #EDEADF;

    /* Gradio 내장 컴포넌트(라디오/슬라이더) 포인트 컬러 오버라이드 */
    --checkbox-background-color-selected: var(--tr-primary);
    --checkbox-background-color-selected-dark: var(--tr-primary);
    --checkbox-border-color-selected: var(--tr-primary);
    --checkbox-label-background-fill-selected: var(--tr-primary);
    --slider-color: var(--tr-primary);
}

.gradio-container {
    max-width: 1050px !important;
    margin: 0 auto !important;
    background: var(--tr-bg) !important;
    font-family: "Pretendard", "Inter", -apple-system, sans-serif;
}

#title-box {
    text-align: center;
    margin-bottom: 12px;
}

#title-box h1 {
    color: var(--tr-text);
    font-weight: 700;
    margin-bottom: 4px;
}

#title-box p {
    color: var(--tr-text-muted);
}

.option-box {
    background: var(--tr-surface) !important;
    border: 1px solid var(--tr-border) !important;
    border-radius: 16px !important;
    padding: 20px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

#chatbot {
    min-height: 420px;
    background: var(--tr-bg) !important;
    border-radius: 16px;
}

/* 사용자 버블만 색을 입히고, AI 응답은 카드 없이 배경 위에 흐르듯 표시 */
#chatbot .panel.user-row {
    background-color: var(--tr-bubble-user) !important;
    border-radius: 18px !important;
}
#chatbot .panel.bot-row {
    background: transparent !important;
}

/* 결과 패널 markdown 표 스타일 */
#result-panel table {
    border-collapse: collapse;
    width: 100%;
}
#result-panel th {
    background: var(--tr-surface);
    border: 1px solid var(--tr-border);
    padding: 8px 12px;
}
#result-panel td {
    border: 1px solid var(--tr-border);
    padding: 8px 12px;
}

#message-input textarea:focus {
    border-color: var(--tr-primary) !important;
}

#send-button {
    min-height: 44px;
    font-weight: 700;
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 12px;
}

#send-button:hover {
    background: var(--tr-primary-hover) !important;
}

@media (prefers-color-scheme: dark) {
    :root {
        --tr-bg: #1F1E1D;
        --tr-surface: #2B2A28;
        --tr-text: #E8E6DC;
        --tr-text-muted: #B5B3A8;
        --tr-border: #3A3835;
        --tr-bubble-user: #3A362E;
    }
}
"""

# Pretendard 웹폰트 실제 로딩 (CUSTOM_CSS의 font-family 지정만으로는 로드되지 않음)
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

    gr.Markdown(
        """
# TripRoute AI 여행 플래너

Solar API와 Agentic Workflow를 활용한 국내 여행 일정 생성 챗봇
""",
        elem_id="title-box",
    )

    with gr.Row():

        # 왼쪽 설정 영역
        with gr.Column(
            scale=1,
            min_width=250,
            elem_classes=["option-box"],
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
                "대화 초기화",
                variant="secondary",
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
        css=CUSTOM_CSS,
        head=HEAD_HTML,
    )
