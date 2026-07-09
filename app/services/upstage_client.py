from typing import Any, Dict, List

from openai import OpenAI

from app.core.config import settings

BASE_URL = "https://api.upstage.ai/v1"

CHAT_MODEL = "solar-pro2"
EMBEDDING_QUERY_MODEL = "solar-embedding-1-large-query"
EMBEDDING_PASSAGE_MODEL = "solar-embedding-1-large-passage"


def _client() -> OpenAI:
    return OpenAI(api_key=settings.UPSTAGE_API_KEY, base_url=BASE_URL)


def chat_completion(messages: List[Dict[str, str]], model: str = CHAT_MODEL) -> str:
    """
    Solar Chat 모델로 답변을 생성합니다.
    """

    response = _client().chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content


def embed_query(text: str) -> List[float]:
    """
    사용자 취향 문장 등 짧은 질의 텍스트를 임베딩합니다.
    """

    response = _client().embeddings.create(model=EMBEDDING_QUERY_MODEL, input=text)
    return response.data[0].embedding


def embed_passages(texts: List[str]) -> List[List[float]]:
    """
    관광지 설명 등 저장 대상 문서 텍스트를 임베딩합니다 (배치 가능).
    """

    response = _client().embeddings.create(model=EMBEDDING_PASSAGE_MODEL, input=texts)
    return [item.embedding for item in response.data]
