# ==============================
# 1단계: 의존성 빌드
# ==============================
FROM python:3.14-slim-trixie AS builder

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN uv sync \
    --frozen \
    --no-dev \
    --no-install-project


# ==============================
# 2단계: 실제 실행 이미지
# ==============================
FROM python:3.14-slim-trixie AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# builder에서 설치한 Python 환경만 복사
COPY --from=builder /app/.venv /app/.venv

# 애플리케이션 소스 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]