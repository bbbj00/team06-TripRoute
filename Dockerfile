FROM python:3.14-slim-trixie

# uv 공식 이미지에서 실행 파일 복사
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_DEV=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# 의존성 파일을 먼저 복사해 Docker 레이어 캐시 활용
COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project

# 프로젝트 파일 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]