# ui/gradio_app.py

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import gradio as gr


# ---------------------------------------------------------
# 프로젝트 루트를 Python 경로에 추가
# ---------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.agents.react_loop import run_triproute_react_loop
from app.utils.formatter import format_trip_plan_markdown


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
"""


# ---------------------------------------------------------
# 여행 계획 생성
# ---------------------------------------------------------
def create_trip_response(
    message: str,
    transport_mode: str,
    people_count: int | float,
) -> str:
    """
    사용자 메시지를 Coordinator에 전달하고,
    Formatter를 통해 Markdown 답변으로 변환합니다.
    """

    normalized_message = (message or "").strip()

    if not normalized_message:
        return "여행 요청을 입력해주세요."

    try:
        normalized_people_count = int(people_count)

        result = run_triproute_react_loop(
            user_input=normalized_message,
            transport_mode=transport_mode,
            people_count=normalized_people_count,
        )

        formatted_result = format_trip_plan_markdown(
            plan=result,
            include_trace=True,
        )

        parser = result.get("condition_summary", {}).get(
            "parser",
            "unknown",
        )

        parser_name = {
            "solar": "Solar API",
            "mock": "Mock fallback",
        }.get(parser, parser)

        header = (
            "여행 계획을 생성했습니다.\n\n"
            f"- 입력 분석: **{parser_name}**\n"
            f"- 이동수단: **{transport_mode}**\n"
            f"- 여행 인원: **{normalized_people_count}명**\n\n"
        )

        return header + formatted_result

    except ValueError as error:
        return (
            "여행 조건을 확인해주세요.\n\n"
            f"- 원인: `{error}`"
        )

    except Exception as error:
        return (
            "여행 계획을 생성하는 중 오류가 발생했습니다.\n\n"
            f"- 오류 종류: `{type(error).__name__}`\n"
            f"- 오류 내용: `{error}`"
        )


# ---------------------------------------------------------
# 챗봇 메시지 처리
# ---------------------------------------------------------
def chat(
    message: str,
    history: list[dict[str, str]] | None,
    transport_mode: str,
    people_count: int | float,
):
    """
    사용자 메시지와 AI 응답을 Gradio messages 형식으로 추가합니다.
    """

    if history is None:
        history = []

    normalized_message = (message or "").strip()

    if not normalized_message:
        return history, ""

    response = create_trip_response(
        message=normalized_message,
        transport_mode=transport_mode,
        people_count=people_count,
    )

    history.append(
        {
            "role": "user",
            "content": normalized_message,
        }
    )

    history.append(
        {
            "role": "assistant",
            "content": response,
        }
    )

    return history, ""


# ---------------------------------------------------------
# 대화 초기화
# ---------------------------------------------------------
def clear_chat():
    return [], DEFAULT_MESSAGE


# ---------------------------------------------------------
# 간단한 CSS
# ---------------------------------------------------------
CUSTOM_CSS = """
.gradio-container {
    max-width: 1050px !important;
    margin: 0 auto !important;
}

#title-box {
    text-align: center;
    margin-bottom: 12px;
}

#title-box h1 {
    margin-bottom: 4px;
}

#chatbot {
    min-height: 520px;
}

#send-button {
    min-height: 44px;
    font-weight: 700;
}

.option-box {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 12px;
}
"""


# ---------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------
with gr.Blocks(
    title="TripRoute AI 여행 플래너",
    css=CUSTOM_CSS,
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
                height=520,
                elem_id="chatbot",
            )

            message_input = gr.Textbox(
                label="여행 요청",
                value=DEFAULT_MESSAGE,
                placeholder=(
                    "여행 지역, 기간, 취향을 입력해주세요."
                ),
                lines=3,
            )

            send_button = gr.Button(
                "여행 계획 생성",
                variant="primary",
                elem_id="send-button",
            )

    gr.Markdown(
        """
> 현재 여행지와 이동정보 일부는 MVP용 Mock 데이터를 사용하며,  
> 입력 조건 분석은 Solar API 또는 Mock fallback으로 처리됩니다.
"""
    )

    # -----------------------------------------------------
    # 이벤트 연결
    # -----------------------------------------------------
    send_button.click(
        fn=chat,
        inputs=[
            message_input,
            chatbot,
            transport_mode,
            people_count,
        ],
        outputs=[
            chatbot,
            message_input,
        ],
    )

    message_input.submit(
        fn=chat,
        inputs=[
            message_input,
            chatbot,
            transport_mode,
            people_count,
        ],
        outputs=[
            chatbot,
            message_input,
        ],
    )

    clear_button.click(
        fn=clear_chat,
        inputs=[],
        outputs=[
            chatbot,
            message_input,
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
    )