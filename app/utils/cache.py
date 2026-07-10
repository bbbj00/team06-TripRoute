import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

CACHE_DIR = Path("data/cache")
DEFAULT_TTL_SECONDS = 60 * 60 * 24  # 카카오/TourAPI 응답은 하루 정도면 충분히 안정적이라 24시간으로 둠


def _cache_path(namespace: str, params: Dict[str, Any]) -> Path:
    # 캐시 키는 namespace + 파라미터 조합의 해시. 파라미터 순서가 달라도 같은 키가 나오도록 정렬함.
    raw = json.dumps(params, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{namespace}_{digest}.json"


def get_cached(namespace: str, params: Dict[str, Any], ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[Any]:
    """
    캐시된 응답이 있고 TTL 안이면 그 데이터를 반환하고, 없거나 만료됐으면 None을 반환합니다.
    """

    path = _cache_path(namespace, params)
    if not path.exists():
        return None

    with open(path, encoding="utf-8") as f:
        cached = json.load(f)

    if time.time() - cached["cached_at"] > ttl_seconds:
        return None

    return cached["data"]


def set_cached(namespace: str, params: Dict[str, Any], data: Any) -> None:
    """
    API 응답을 JSON 캐시 파일로 저장합니다.
    """

    path = _cache_path(namespace, params)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"cached_at": time.time(), "params": params, "data": data}, f, ensure_ascii=False)


def cached_call(
    namespace: str,
    params: Dict[str, Any],
    fetch_fn: Callable[[], Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Any:
    """
    캐시가 있으면 그대로 반환하고, 없으면 fetch_fn()을 호출해서 결과를 캐시에 저장한 뒤 반환합니다.
    API 호출 결과를 그대로 감싸서 쓰는 용도 (예: kakao_mobility.get_route).
    """

    cached = get_cached(namespace, params, ttl_seconds)
    if cached is not None:
        return cached

    data = fetch_fn()
    set_cached(namespace, params, data)
    return data
