# app/services/upstage_client.py

import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings


BASE_URL = "https://api.upstage.ai/v1"

CHAT_MODEL = "solar-pro2"
EMBEDDING_QUERY_MODEL = "solar-embedding-1-large-query"
EMBEDDING_PASSAGE_MODEL = "solar-embedding-1-large-passage"


DEFAULT_PARSE_RESULT = {
    "city": "강릉",
    "season": "여름",
    "duration": "1박 2일",
    "travel_style": ["바다", "감성 카페", "먹거리"],
    "schedule_intensity": "여유로운 일정",
}


def _client() -> OpenAI:
    """
    Upstage OpenAI-compatible API 클라이언트를 생성합니다.
    """

    api_key = settings.UPSTAGE_API_KEY

    if not api_key:
        raise RuntimeError("UPSTAGE_API_KEY가 설정되어 있지 않습니다.")

    return OpenAI(
        api_key=api_key,
        base_url=BASE_URL,
    )


def chat_completion(
    messages: List[Dict[str, str]],
    model: str = CHAT_MODEL,
) -> str:
    """
    Solar Chat 모델로 일반 답변을 생성합니다.
    """

    response = _client().chat.completions.create(
        model=model,
        messages=messages,
    )

    return response.choices[0].message.content or ""


def embed_query(text: str) -> List[float]:
    """
    사용자 취향 문장 등 질의 텍스트를 임베딩합니다.
    """

    response = _client().embeddings.create(
        model=EMBEDDING_QUERY_MODEL,
        input=text,
    )

    return response.data[0].embedding


def embed_passages(texts: List[str]) -> List[List[float]]:
    """
    관광지 설명 등 저장 대상 문서를 임베딩합니다.
    """

    response = _client().embeddings.create(
        model=EMBEDDING_PASSAGE_MODEL,
        input=texts,
    )

    return [item.embedding for item in response.data]


def parse_user_input_mock(user_input: str) -> dict[str, Any]:
    """
    Solar API 호출 실패 시 사용하는 Mock 입력 파서입니다.
    """

    return {
        **DEFAULT_PARSE_RESULT,
        "_parser": "mock",
    }


def _extract_json(text: str) -> dict[str, Any]:
    """
    Solar 응답 문자열에서 JSON 객체를 추출합니다.
    """

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("Solar 응답에서 JSON 객체를 찾지 못했습니다.")

    return json.loads(match.group())


def _normalize_parse_result(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Solar 파싱 결과의 누락값과 자료형을 정규화합니다.
    """

    travel_style = (
        data.get("travel_style")
        or DEFAULT_PARSE_RESULT["travel_style"]
    )

    if isinstance(travel_style, str):
        travel_style = [travel_style]

    return {
        "city": (
            data.get("city")
            or DEFAULT_PARSE_RESULT["city"]
        ),
        "season": (
            data.get("season")
            or DEFAULT_PARSE_RESULT["season"]
        ),
        "duration": (
            data.get("duration")
            or DEFAULT_PARSE_RESULT["duration"]
        ),
        "travel_style": travel_style,
        "schedule_intensity": (
            data.get("schedule_intensity")
            or DEFAULT_PARSE_RESULT["schedule_intensity"]
        ),
        "_parser": "solar",
    }


def parse_user_input_with_solar(
    user_input: str,
) -> dict[str, Any]:
    """
    사용자 자연어 요청을 Solar API로 여행 조건 JSON으로 변환합니다.
    """

    model = os.getenv("UPSTAGE_MODEL", CHAT_MODEL)

    system_prompt = """
너는 여행 일정 생성 서비스의 입력 파서다.
사용자의 자연어 여행 요청에서 여행 조건을 JSON으로만 추출해라.

반드시 아래 JSON 형식으로만 답변해라.
설명 문장, Markdown, 코드블록은 쓰지 마라.

{
  "city": "도시명",
  "season": "계절 또는 시기",
  "duration": "여행 기간",
  "travel_style": ["취향1", "취향2"],
  "schedule_intensity": "여유로운 일정 또는 빡빡한 일정"
}
"""

    response = _client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_input,
            },
        ],
        temperature=0,
    )

    content = response.choices[0].message.content or ""
    data = _extract_json(content)

    return _normalize_parse_result(data)


def parse_trip_request(
    user_input: str,
) -> tuple[dict[str, Any], list[str]]:
    """
    Solar 입력 파싱을 시도하고 실패하면 Mock parser를 사용합니다.
    """

    try:
        parsed = parse_user_input_with_solar(user_input)
        return parsed, []

    except Exception as error:
        fallback = parse_user_input_mock(user_input)

        warnings = [
            (
                "Solar API 파싱 실패로 Mock 파싱을 사용했습니다. "
                f"원인: {error}"
            )
        ]

        return fallback, warnings