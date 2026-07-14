# app/services/upstage_client.py

import json
import os
import re
from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings
from app.core.prompts import (
    COORDINATOR_PARSE_SYSTEM_PROMPT,
    FINANCIAL_USEFEE_PARSE_SYSTEM_PROMPT,
)


BASE_URL = "https://api.upstage.ai/v1"

CHAT_MODEL = "solar-pro2"
EMBEDDING_QUERY_MODEL = "solar-embedding-1-large-query"
EMBEDDING_PASSAGE_MODEL = "solar-embedding-1-large-passage"


DEFAULT_PARSE_RESULT = {
    "city": "강릉",
    "season": "여름",
    "duration": "1박 2일",
    "travel_style": ["바다", "감성 카페", "먹거리"],
    "must_include_places": [],
    "schedule_intensity": "여유로운 일정",
    "prefer_local": False,
    "prefer_budget": False,
    "is_peak_season": True,
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


# 부정 문맥 감지용 키워드 (Mock parser fallback용). "돈 아끼지 않고", "여름은
# 피하고"처럼 키워드 바로 앞/뒤에 부정 표현이 붙어 뜻이 반전되는 흔한 패턴만
# 걸러내는 간단한 근사치이며, 완전한 부정 감지를 보장하지는 않는다.
NEGATION_MARKERS = ["안", "않", "말고", "아니", "피하"]


def _is_negated(user_input: str, keyword: str) -> bool:
    idx = user_input.find(keyword)

    if idx == -1:
        return False

    window_start = max(0, idx - 6)
    window_end = min(len(user_input), idx + len(keyword) + 8)
    window = user_input[window_start:window_end]

    return any(marker in window for marker in NEGATION_MARKERS)


# "가성비", "저렴하게" 같은 예산 중시 표현 감지용 키워드 (Mock parser fallback용, prefer_local과 동일한 이유)
PREFER_BUDGET_KEYWORDS = [
    "가성비",
    "저렴",
    "알뜰",
    "돈 아끼",
    "저가",
    "budget",
]


def _detect_prefer_budget(user_input: str) -> bool:
    return any(
        keyword in user_input and not _is_negated(user_input, keyword)
        for keyword in PREFER_BUDGET_KEYWORDS
    )


# 국내 숙박 성수기 시즌 감지용 키워드 (Mock parser fallback용). Solar는 날짜/시기를
# 문맥으로 판단하지만, Mock은 규칙 기반이라 정교한 날짜 계산 대신 키워드로만 근사한다.
PEAK_SEASON_KEYWORDS = [
    "여름",
    "성수기",
    "휴가철",
    "명절",
    "설날",
    "추석",
    "연휴",
    "크리스마스",
    "연말",
]


def _detect_peak_season(user_input: str) -> bool:
    return any(
        keyword in user_input and not _is_negated(user_input, keyword)
        for keyword in PEAK_SEASON_KEYWORDS
    )


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


# 슬롯 교체 후속 요청("2일차 점심만 바꿔줘") 감지용 시간대 키워드. route_planner의
# 실제 daily_schedule time_slot 값과 정확히 일치해야 한다(순서는 길게 겹치는 표현을
# 먼저 매칭하도록 "늦은 오후"를 "오후"보다 앞에 둠).
TIME_SLOT_KEYWORDS = ["늦은 오후", "오전", "점심", "오후", "저녁", "체크인"]


def _detect_target_day(user_input: str) -> int | None:
    """
    "2일차", "Day 2", "둘째 날" 처럼 특정 하루를 콕 짚은 표현에서 며칠차인지 뽑아낸다.
    Mock parser는 대화 맥락을 못 보므로, target_time_slot과 같이 있을 때만 의미가
    있어(parse_user_input_mock에서 둘 다 있을 때만 채움) 오탐(단순히 "3일"이 기간
    설명으로 쓰인 경우 등) 영향을 줄인다.
    """
    match = re.search(r"(\d+)\s*일\s*[차째]", user_input)
    if match:
        return int(match.group(1))

    match = re.search(r"[Dd]ay\s*(\d+)", user_input)
    if match:
        return int(match.group(1))

    return None


def _detect_target_time_slot(user_input: str) -> str | None:
    for slot in TIME_SLOT_KEYWORDS:
        if slot in user_input:
            return slot

    return None


VALID_TIME_SLOTS = set(TIME_SLOT_KEYWORDS)


def _normalize_target_day(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and int(value) > 0:
        return int(value)
    return None


def _normalize_target_time_slot(value: Any) -> str | None:
    if isinstance(value, str) and value in VALID_TIME_SLOTS:
        return value
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
    city/prefer_local/prefer_budget/is_peak_season만큼은 키워드 매칭으로 실제
    user_input을 반영합니다.
    """

    target_day = _detect_target_day(user_input)
    target_time_slot = _detect_target_time_slot(user_input)
    # 둘 다 있을 때만 "특정 일차의 특정 시간대 교체" 신호로 본다 — 하나만 있으면
    # (예: "3일 여행"의 "3일"엔 시간대 언급이 없음) 기간 설명과 헷갈릴 위험이 크다.
    if target_day is None or target_time_slot is None:
        target_day = None
        target_time_slot = None

    return {
        **DEFAULT_PARSE_RESULT,
        "city": _detect_city(user_input) or DEFAULT_PARSE_RESULT["city"],
        "prefer_local": _detect_prefer_local(user_input),
        "prefer_budget": _detect_prefer_budget(user_input),
        "is_peak_season": _detect_peak_season(user_input),
        "target_day": target_day,
        "target_time_slot": target_time_slot,
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

    # 그리디 정규식(\{.*\})은 부연설명 안에 별도 중괄호가 있으면 첫 '{'부터
    # 마지막 '}'까지를 통째로 묶어버려 서로 다른 JSON 블록을 이어붙인 깨진
    # 문자열을 만든다. 대신 첫 '{'부터 중괄호 깊이를 세어 짝이 맞는 지점까지만
    # 후보로 삼고, 파싱에 실패하면 다음 '{'로 넘어가며 재시도한다.
    start = text.find("{")

    while start != -1:
        depth = 0

        for index in range(start, len(text)):
            char = text[index]

            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1

                if depth == 0:
                    candidate = text[start : index + 1]

                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break

        start = text.find("{", start + 1)

    raise ValueError("Solar 응답에서 JSON 객체를 찾지 못했습니다.")


def _normalize_parse_result(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Solar 파싱 결과의 누락값과 자료형을 정규화합니다.
    """

    travel_style = data.get("travel_style")
    if travel_style is None:
        # 키 자체가 없을 때만 데모 기본값을 적용한다. 빈 리스트([])는 "취향
        # 없음"이라는 유효한 응답이므로 그대로 존중해야 한다.
        travel_style = DEFAULT_PARSE_RESULT["travel_style"]

    if isinstance(travel_style, str):
        travel_style = [travel_style]

    must_include_places = data.get("must_include_places", [])
    if isinstance(must_include_places, str):
        must_include_places = [must_include_places]

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
        "must_include_places": must_include_places,
        "schedule_intensity": (
            data.get("schedule_intensity")
            or DEFAULT_PARSE_RESULT["schedule_intensity"]
        ),
        "prefer_local": bool(data.get("prefer_local", False)),
        "prefer_budget": bool(data.get("prefer_budget", False)),
        "is_peak_season": bool(data.get("is_peak_season", False)),
        "target_day": _normalize_target_day(data.get("target_day")),
        "target_time_slot": _normalize_target_time_slot(data.get("target_time_slot")),
        "_parser": "solar",
    }


# parse 결과 JSON 스키마에 실제로 속하는 필드만. condition_summary(coordinator.py의
# finalize_node 출력)에는 transport_mode/people_count/parser/data_source 같은
# 스키마 외 필드도 섞여 있어서, 이전 대화를 합성 assistant 메시지로 되돌려줄 때
# 이 필드들만 걸러내야 모델이 스키마 밖 키를 그대로 따라 하지 않는다.
_PARSE_SCHEMA_FIELDS = (
    "city",
    "season",
    "duration",
    "travel_style",
    "must_include_places",
    "schedule_intensity",
    "prefer_local",
    "prefer_budget",
    "is_peak_season",
)


def _build_solar_messages(
    user_input: str,
    previous_condition_summary: dict[str, Any] | None,
) -> list[dict[str, str]]:
    messages = [
        {
            "role": "system",
            "content": COORDINATOR_PARSE_SYSTEM_PROMPT,
        },
    ]

    if previous_condition_summary:
        previous_user_input = previous_condition_summary.get("user_input")
        previous_parsed = {
            field: previous_condition_summary.get(field)
            for field in _PARSE_SCHEMA_FIELDS
            if field in previous_condition_summary
        }

        if previous_user_input and previous_parsed:
            messages.append({"role": "user", "content": previous_user_input})
            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps(previous_parsed, ensure_ascii=False),
                }
            )

    messages.append({"role": "user", "content": user_input})

    return messages


def parse_user_input_with_solar(
    user_input: str,
    previous_condition_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    사용자 자연어 요청을 Solar API로 여행 조건 JSON으로 변환합니다.

    previous_condition_summary(직전 턴의 condition_summary)가 주어지면, 이전
    사용자 메시지/파싱 결과를 대화 맥락으로 같이 보내 후속 요청("카페 말고
    맛집 위주로 바꿔줘" 등)이 이전 조건을 이어받아 갱신되도록 한다.
    """

    model = os.getenv("UPSTAGE_MODEL", CHAT_MODEL)

    response = _client().chat.completions.create(
        model=model,
        messages=_build_solar_messages(user_input, previous_condition_summary),
        temperature=0,
    )

    content = response.choices[0].message.content or ""
    data = _extract_json(content)

    return _normalize_parse_result(data)


def parse_trip_request(
    user_input: str,
    previous_condition_summary: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Solar 입력 파싱을 시도하고 실패하면 Mock parser를 사용합니다.
    """

    try:
        parsed = parse_user_input_with_solar(user_input, previous_condition_summary)
        return parsed, []

    except Exception as error:
        fallback = parse_user_input_mock(user_input)

        warnings = [
            (
                "Solar API 파싱 실패로 Mock 파싱을 사용했습니다. "
                f"원인: {error}"
            )
        ]

        if previous_condition_summary:
            # Mock parser는 키워드 매칭만 하고 대화 맥락을 전혀 안 보므로, 후속 턴에서
            # mock으로 떨어지면 이전 조건이 그대로 유실된다 — 조용히 품질이 떨어지는
            # 대신 사용자가 알아챌 수 있게 경고를 남긴다.
            warnings.append(
                "이전 대화 맥락을 반영하지 못했습니다 (Mock fallback)."
            )

        return fallback, warnings


def parse_usefee_amount(usefee_text: str) -> int | None:
    """
    TourAPI usefee(이용요금) 비정형 텍스트에서 성인 1인 기준 대표 금액을 추출합니다.
    무료면 0, 특정할 수 없으면 None을 반환합니다. 파싱 실패(API 오류 등) 시에도 None을
    반환해서 호출부가 fallback 추정치를 쓰도록 합니다.
    """

    if not usefee_text or not usefee_text.strip():
        return None

    model = os.getenv("UPSTAGE_MODEL", CHAT_MODEL)

    try:
        response = _client().chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": FINANCIAL_USEFEE_PARSE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": usefee_text,
                },
            ],
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        data = _extract_json(content)

        if not isinstance(data, dict):
            return None

        amount = data.get("amount")
    except Exception:
        return None

    if amount is None:
        return None

    try:
        return int(amount)
    except (TypeError, ValueError):
        return None