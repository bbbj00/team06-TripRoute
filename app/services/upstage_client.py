# app/services/upstage_client.py

import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.core.prompts import COORDINATOR_PARSE_SYSTEM_PROMPT


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
    "prefer_local": False,
}

# "로컬만 아는 곳", "사람 안 몰리는 곳" 같은 hidden-gem 선호 표현 감지용 키워드.
# Solar 파싱이 실패해 Mock parser로 넘어갔을 때도 이 신호만큼은 규칙 기반으로 살리기 위해 씀.
PREFER_LOCAL_KEYWORDS = [
    "로컬",
    "현지인",
    "숨은",
    "한적한",
    "덜 붐비는",
    "붐비지 않는",
    "사람 안 몰리는",
    "사람 없는",
    "관광객 없는",
    "핫플 말고",
    "유명하지 않은",
]


def _detect_prefer_local(user_input: str) -> bool:
    return any(keyword in user_input for keyword in PREFER_LOCAL_KEYWORDS)


# 실제 관광지 데이터(Supabase places 테이블)를 확보해둔 도시만 감지 대상으로 함
# (Step 4 RAG 수집 대상, docs/project_plan.md 참고). 목록에 없는 도시를 입력하면
# Mock parser는 기존처럼 DEFAULT_PARSE_RESULT["city"](강릉)로 대체한다.
KNOWN_CITIES = [
    "강릉", "속초", "춘천", "부산", "제주",
    "경주", "전주", "여수", "인천", "서울",
]


def _detect_city(user_input: str) -> str | None:
    for city in KNOWN_CITIES:
        if city in user_input:
            return city

    return None


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

    season/duration/travel_style/schedule_intensity는 고정 데모 값을 그대로 쓰지만,
    city와 prefer_local만큼은 키워드 매칭으로 실제 user_input을 반영합니다.
    """

    return {
        **DEFAULT_PARSE_RESULT,
        "city": _detect_city(user_input) or DEFAULT_PARSE_RESULT["city"],
        "prefer_local": _detect_prefer_local(user_input),
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
        "prefer_local": bool(data.get("prefer_local", False)),
        "_parser": "solar",
    }


def parse_user_input_with_solar(
    user_input: str,
) -> dict[str, Any]:
    """
    사용자 자연어 요청을 Solar API로 여행 조건 JSON으로 변환합니다.
    """

    model = os.getenv("UPSTAGE_MODEL", CHAT_MODEL)

    response = _client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": COORDINATOR_PARSE_SYSTEM_PROMPT,
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