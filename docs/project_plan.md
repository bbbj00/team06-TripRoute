# TripRoute 프로젝트 실행 계획 (Project Plan)

> 본 문서는 README의 개발 로드맵을 기반으로, **날짜 없이 "무엇을 해야 하는가"** 중심으로 작업 항목을 정리한 실행 계획서입니다.
> 각 단계는 순차적으로 진행하되, 외부 API 연결(Step 2)과 State/Agent 기본 흐름(Step 3)은 병행 가능합니다.

---

## Step 0. 개발 환경 및 사전 준비

- [x] `uv` 기반 가상환경 세팅 (`pyproject.toml` + `uv.lock`, FastAPI/Gradio/LangGraph/langchain/supabase/httpx/python-dotenv/langfuse 등)
- [x] 팀원 각자 `uv sync` 실행해 동일 환경 재현
- [x] `.env.example` 작성 (Upstage / TourAPI / Kakao Mobility / Supabase / Langfuse 키)
- [x] `.env` 생성 및 실제 API Key 입력 (Git에 커밋되지 않도록 주의)
- [x] `.gitignore`에 `.env`, `.venv`, `__pycache__`, `data/cache/`, `data/raw/` 포함 확인
- [x] 각 외부 API 계정 발급 및 키 확보
  - [x] Upstage Solar API 키
  - [x] 공공데이터포털(data.go.kr) 인증키 발급 — **아래 두 서비스에 각각 "활용신청" (키 값은 계정당 1개 공통, `TOUR_API_KEY` 하나로 둘 다 호출)**
    - [x] 한국관광공사_국문 관광정보 서비스_GW (ID 15101578) — 일반 관광정보
    - [x] 한국관광공사_관광지별 연관 관광지 정보 (ID 15128560) — 연관 관광지
  - [x] 카카오모빌리티 API 키
  - [x] Supabase 프로젝트 생성 + URL/KEY
  - [x] Langfuse 프로젝트 생성 + 키

---

## Step 1. 프로젝트 기본 구조 구성

- [x] README의 폴더 구조에 맞춰 디렉토리 및 `__init__.py` 생성
  - [x] `app/` (core, graph, agents, services, rag, utils, schemas)
  - [x] `ui/`, `data/` (raw, cache, sample), `docs/`, `tests/`
- [x] `app/core/config.py` — `.env` 환경변수 로드 로직 구현
- [x] `app/main.py` — FastAPI 앱 초기화 및 기본 실행 확인 (`uvicorn app.main:app --reload`)
- [ ] `ui/gradio_app.py` — Gradio 기본 UI 실행 확인 (파일은 생성됐지만 내용 비어있음 — 구현 필요)
- [ ] `app/schemas/` — 요청/응답 Pydantic 모델 정의
  - [x] `request.py` (user_input, transport_mode, people_count)
  - [x] `response.py` (condition_summary, daily_schedule, route_summary, cost_summary, warnings)
  - [ ] `place.py` (관광지 데이터 모델, 파일은 생성됐지만 내용 비어있음 — 구현 필요)

---

### Mock ReAct Loop 프로토타입 — Step 1~3 선행 작업

- [x] `app/agents/react_loop.py` — Thought → Action → Observation → Final 흐름의 Mock ReAct Loop 구현
- [x] `app/tools/mock_tools.py` — `search_places` / `get_related_places` / `get_route_info` / `estimate_cost` Mock Tool 구현
- [x] `app/tools/schemas.py` — `ToolResult` 스키마 정의 (⚠️ `ToolCall`은 정의만 되어있고 실제로는 미사용 — 아래 참고)
- [x] `tests/test_react_loop.py`, `tests/conftest.py` — Mock ReAct Loop pytest 시나리오
- [ ] 위 Mock Tool들을 Step 2의 실제 API 서비스(`tour_api.py`, `related_place_api.py`, `kakao_mobility.py`)로 교체
- [ ] `react_loop.py`를 Step 3의 Coordinator/Route Planner/Financial 3-Agent + LangGraph 구조로 리팩터링
- [x] **설계 결정**: TripRoute는 절차가 항상 고정된 파이프라인이라 Tool Calling(LLM이 다음 행동을
      스스로 판단하는 ReAct 방식)을 도입하지 않기로 함. 대신 LangGraph 고정 그래프 + 각 Agent 내부의
      좁은 범위 LLM 호출(입력 분석/문장 생성/텍스트 구조화) 방식으로 감. 상세 근거는
      `docs/architecture.md` 참고. `app/tools/` 폴더는 지금 지우지 않고 유지 — Step 2/3 리팩터링
      시점에 팀 논의 후 삭제 여부 재결정.

---

## Step 2. 외부 API 연결 테스트

- [x] `app/services/tour_api.py` — 관광지 검색(`searchKeyword2`)/상세공통(`detailCommon2`)/소개정보(`detailIntro2`, 운영시간·usefee) 호출 및 테스트 완료
- [x] `app/services/related_place_api.py` — 연관 관광지 조회(`areaBasedList1`, `searchKeyword1`) 호출 및 테스트 완료
- [x] `app/services/kakao_mobility.py` — 길찾기(거리·소요시간·택시요금·통행료) 호출 및 테스트 완료
- [x] `app/services/upstage_client.py` — Solar LLM(`solar-pro2`) + Embedding(query/passage, 4096차원) 호출 및 테스트 완료
- [x] `app/services/supabase_client.py` — Supabase 연결 확인 + pgvector 확장/테이블/검색 함수 세팅 완료 (`insert_place`, `search_similar_places`로 실제 강릉 관광지 임베딩 저장·유사도 검색까지 테스트 성공, Step 4 RAG 기반 작업 미리 완료)
- [ ] `app/utils/cache.py` — API 응답 캐싱(JSON/CSV) 구현
- [ ] `data/sample/` — API 실패 대비 샘플 데이터 확보 (`sample_places.json`, `sample_routes.json`, `sample_plan.json`)

---

## Step 3. State 및 Agent 기본 흐름 구현

- [x] `app/core/state.py` — `TripRouteState` TypedDict 정의 (README 9절 필드 기준)
- [ ] `app/core/prompts.py` — Agent별 프롬프트 템플릿 관리
- [ ] `app/agents/coordinator.py` — 자연어 입력 분석 및 조건 추출 (도시·계절·기간·취향·일정강도·이동수단·인원수)
  - [ ] "로컬만 아는 곳/사람 안 몰리는 곳" 같은 표현을 인식해서 `condition_summary`에 hidden-gem
        선호 신호(예: `prefer_local`)로 남기기 — LLM이 의도는 인식하지만 실제 반영은 Route Planner가 해야 함
- [ ] `app/agents/route_planner.py` — 관광지 후보 생성 기본 로직
  - [ ] `places.review_count`(Google Places 연동) 기반으로, `prefer_local` 신호가 있으면 리뷰 수
        낮은 순 우선 정렬 또는 리뷰 수 상위 장소 제외하는 필터링 로직 추가
- [ ] `app/agents/financial.py` — 기본 비용 계산 로직
- [ ] `app/graph/nodes.py` — 각 Agent를 LangGraph 노드로 래핑
- [ ] `app/graph/edges.py` — Agent 실행 순서 및 조건 분기 정의
- [ ] `app/graph/workflow.py` — 전체 그래프 조립 (Coordinator → Route Planner → Financial → Coordinator)
- [ ] Supabase 기반 LangGraph Checkpoint 저장 연결
- [ ] `/trip/plan` 엔드포인트에서 Workflow end-to-end 실행 확인

---

## Step 4. RAG 구현

- [ ] 관광지 설명 데이터 수집 (TourAPI 개요 텍스트)
- [ ] `app/rag/embedder.py` — Upstage Embedding으로 관광지 설명 벡터화
- [ ] `app/rag/vector_store.py` — Supabase pgvector 테이블 생성 및 임베딩 저장
- [ ] `app/rag/retriever.py` — 사용자 취향 문장 임베딩 → 유사도 검색
- [ ] Coordinator/Route Planner에서 RAG 검색 결과 연동
- [ ] RAG 유사도 점수를 Route Planner 추천 로직에 반영

---

## Step 5. 동선 및 비용 계산 고도화

- [ ] `app/utils/transport_rules.py` — 대중교통 휴리스틱 (시간 ×1.5~2.0, 거리 기반 요금)
- [ ] `app/utils/cost_rules.py` — 식비·카페비·숙박비·입장료 추정 규칙
- [ ] Route Planner — 카카오 API 기반 구간별 이동시간 계산 및 State 기록
- [ ] Route Planner — 하루 일정 과밀도 체크 (일정 강도·계절 반영)
- [ ] Financial Agent — 이동수단별 비용 분기 (자차/렌터카/택시/대중교통)
- [ ] Financial Agent — TourAPI usefee 비정형 텍스트 파싱 (Upstage 구조화 활용)
- [ ] Financial Agent — State의 route_segments를 읽어 총 예상 비용 산정

---

## Step 6. 최종 출력 포맷 구성

- [ ] `app/utils/formatter.py` — State → 최종 응답 포맷 변환
- [ ] 조건 요약 출력
- [ ] 시간대별 일정표(Day/시간대/장소/추천이유/동선메모) 출력
- [ ] 예상 비용표 출력 (교통비·식비·카페비·입장료·숙박비·총액)
- [ ] 주의사항(warnings) 출력 — 대중교통 추정치 안내 문구 필수 포함
- [ ] Gradio UI에서 결과 렌더링 (표 형태)
- [ ] **UX: 파이프라인 진행상황 표시 + 최종 문장 스트리밍**
  - [ ] 앞 단계(관광지 검색 → RAG → 동선 계산 → 비용 계산) 진행 중 Gradio 상태 메시지 표시
        (예: "관광지 찾는 중...", "동선 계산 중...", "비용 계산 중...")
  - [ ] Coordinator의 최종 문장 생성(추천 이유·일정 설명) 부분은 Upstage `stream=True` +
        Gradio `yield` 기반으로 타이핑 효과 스트리밍 (SSE 직접 구현 불필요)
  - [ ] 주의: `cost_summary`/`route_summary` 같은 계산된 수치 데이터는 스트리밍 대상이 아니라
        계산 완료 시 한 번에 표시됨 — 스트리밍은 자연어 텍스트 부분에만 적용

---

## Step 7. 테스트 및 시연 준비

- [ ] `tests/test_route_planner.py` — 동선 설계 로직 테스트
- [ ] `tests/test_financial.py` — 비용 계산 로직 테스트
- [ ] `tests/test_rag.py` — RAG 검색 테스트
- [ ] API 실패 시 `data/sample/` fallback 처리 검증
- [ ] 시연용 대표 시나리오(예: 강릉 1박2일) end-to-end 동작 확인
- [ ] `docs/` 문서 정리 (architecture, api_notes, state_design)
- [ ] 발표용 아키텍처 다이어그램 및 실행 화면 캡처

---

## Step 8. Docker 컨테이너화 및 CI/CD 기반 GCP 배포

- [ ] 배포 대상 서비스 확정 (Cloud Run 유력 — FastAPI를 컨테이너로 띄우고 Gradio도 같은 서비스 또는 별도 서비스로 서빙)
- [ ] `Dockerfile` 작성 및 로컬 컨테이너 실행 확인
- [ ] `.env`의 API Key/Secret을 GCP Secret Manager(또는 Cloud Run 환경변수)로 이관
- [ ] CI/CD 파이프라인 구성 (예: GitHub Actions → 컨테이너 이미지 빌드 → Artifact Registry push → Cloud Run 배포 자동화)
- [ ] Cloud Run 배포 및 외부 접속 URL로 최종 시연 확인

---

## 핵심 설계 원칙 (전 단계 공통 준수)

- **State 중심 결합**: Agent 간 직접 호출 대신 `TripRouteState`를 매개로 데이터 공유
- **Coordinator가 흐름 제어**: 입력 분석 → 하위 Agent 디스패치 → 최종 조립 담당
- **대중교통은 휴리스틱**: 실시간 환승 API 미사용, 결과에 반드시 추정치 안내 문구 포함
- **Fallback 우선**: API 장애/호출 제한 대비 캐시·샘플 데이터 상시 유지
- **MVP 범위 고정**: 지도 시각화·실시간 재최적화·예약/결제·로그인은 제외

---

## MVP 범위 요약

**포함**: 자연어 입력 · 이동수단 선택 · 인원수 · 관광지 후보 조회 · RAG 취향 매칭 · 카카오 기반 동선 · 대중교통 휴리스틱 · 일정표 · 예상 비용 · Gradio UI · FastAPI 엔드포인트 · GCP 배포

**제외**: 숙소/식당 예약 · 결제/예매 · 실시간 교통 · 실시간 대중교통 환승 · 지도 시각화 · 로그인 · 장기 개인화 · 모바일 앱
