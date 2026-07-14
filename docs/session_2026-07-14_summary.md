# 2026-07-14 작업 정리

전날(`docs/session_2026-07-13_summary.md`) 이후 진행한 작업을 주제별로 정리합니다.
1~5는 이미 커밋/병합 완료(`16b2817`), 6~7은 이어진 세션에서 새로 진행한 작업입니다.

---

## 1. 로그인 모달 / 최근 대화 버그 수정 (`ui/gradio_app.py`)

- **X 버튼으로 모달이 안 닫히던 문제**: `#auth-modal`/`#auth-overlay`에 걸어둔 커스텀 CSS의
  `min-height`/`position: fixed` 같은 `!important` 크기 지정이 Gradio의 내부 visible=False
  처리(크기를 접으려는 방식)와 충돌해서, 내용만 사라지고 빈 박스가 계속 화면에 남았음.
  → JS로 `.hide` 클래스를 직접 토글하는 방식으로 교체(`OPEN_MODAL_JS`/`CLOSE_MODAL_JS`/
  `CLOSE_MODAL_ON_AUTH_SUCCESS_JS`).
- **로그인/회원가입 성공 시 모달이 안 닫히던 문제**: 성공 시 자동으로 닫히는 로직이 원래
  없었음 → 성공 시(`logged-in-group`이 실제로 렌더링됐는지로 판단) 자동 닫힘 추가.
- **"최근 대화" 클릭 시 `load_session`에 로그인 정보가 `None`으로 넘어오던 문제**:
  `access_token_state`/`recent_sessions_state`를 `session_radio.change`의 입력으로 쓰면
  Gradio 6.20에서 값이 None으로 넘어오는 현상을 재현했지만 정확한 내부 원인은 못 찾음.
  → 항상 정상적으로 넘어오는 `auth_browser_state`(user_id 포함)만으로 직접 조회하도록
  `load_session` 재작성.
- **UX 개선**: 로그인하면 모달을 다시 열 필요 없이 **사이드바에 바로** "환영합니다 /
  로그아웃 / 최근 대화" 목록이 보이도록 `logged-in-group`을 모달 밖 사이드바로 이동.
  "로그인 / 내 정보" 버튼은 로그아웃 상태일 때만 보임.

## 2. 대화 기록 저장 RLS 우회 (`app/core/config.py`, `app/services/supabase_client.py`, `app/services/chat_store.py`)

- `chat_store`가 anon(publishable) 키를 쓰고 있어서 RLS에 막혀 `chat_sessions`/
  `chat_messages` insert가 **항상 조용히 실패**하고 있었음(예외가 `except: pass`로 삼켜져서
  아무도 몰랐음 — 로그인해도 대화 기록이 저장된 적이 없었을 수 있음).
- `SUPABASE_SERVICE_KEY`(service_role)를 분리 도입 → `get_service_client()` 추가,
  `chat_store`만 이 클라이언트를 쓰도록 변경. 사용자가 `.env`에 실제 키 추가 완료, 실측 확인.

## 3. 식비·카페비를 Google Places 가격대(priceLevel)로 실측 연동 (`app/agents/financial.py`, `app/utils/cost_rules.py`, `app/services/google_places_api.py`)

- 기존엔 식비/카페비 모두 인원×일수 고정 단가였음 → `priceLevel`(FREE~VERY_EXPENSIVE) 조회해서
  실제 장소별 가격대 기반으로 계산, 매칭 실패 시에만 기존 고정 단가로 폴백.
- 카페/음식점 구분은 이름에 "카페/커피/cafe/coffee" 키워드 + 국내 주요 카페 브랜드
  (스타벅스/빽다방/투썸플레이스 등) 목록으로 판별.

## 4. 멀티 에이전트(리뷰+비판+수정) 패널로 Route Planner/Financial/Graph/Upstage 점검

리뷰 4개 관점 → 발견마다 비판 에이전트 3인 반박 검증(2인 이상 반박하면 탈락) → 확정된 것만
파일별로 수정하는 워크플로 실행. 18건 발견, 17건 확정, 6개 파일 수정, pytest 75개로 회귀 확인 +
직접 diff 재검토 및 실측 재검증.

- `financial.py`: 렌터카 비용이 경로 구간(leg) 수만큼 중복 청구되던 버그(기존에 있었지만
  안 쓰이던 `estimate_rental_car_cost`를 대신 사용), 음식점/카페가 입장료로도 이중 과금되던
  버그.
- `cache.py`: 병렬 조회 중 캐시 파일이 동시 쓰기로 깨질 수 있던 문제(원자적 교체+락),
  캐시된 값이 `None`이면 매번 재조회하던 문제.
- `route_planner.py`: 스레드풀 워커에서 `TourAPIError`만 잡고 다른 예외는 전파돼 전체 요청이
  죽던 문제, 숙박 요금/필수 방문지 검색 병렬화, 필수 방문지 중복 삽입 버그.
- `graph/nodes.py`: 비용 계산 실패 시 이미 계산된 일정/동선까지 통째로 날아가던 문제(최소
  추정치 fallback 추가), warnings 상태 중복 누적 문제.
- `upstage_client.py`: JSON 파싱이 부연설명 속 중괄호에 깨지던 문제(균형 괄호 스캔으로
  교체), 빈 취향 리스트를 데모 기본값으로 덮어쓰던 문제, `parse_usefee_amount` 크래시 방어,
  "돈 아끼지 않고"/"여름은 피하고" 같은 부정 문맥 오탐 방지.
- `state.py`: `must_include_places` 필드가 State 타입 선언에서 빠져 있던 것.

## 5. UI/UX 추가 버그 수정

- **챗봇 안내 메시지 줄바꿈 과다**: `WELCOME_MESSAGE`에 실제 개행과 `<br><br>`가 같이 있어
  마크다운 렌더링 시 두 배로 벌어지던 문제 → 개행 제거, `<br>` 태그로만 간격 제어.
- **사용자 메시지 말풍선 끝에 여백이 보이던 문제**: Gradio가 메시지를 마크다운으로 렌더링할
  때 `<p>` 뒤에 항상 개행 문자를 하나 더 붙이는데, `white-space: pre-wrap`이라 배경색 있는
  유저 말풍선에서만 그 여백이 보였음(봇 답변은 배경이 투명해서 안 보였을 뿐) → CSS로
  `.message.user p:last-child { margin-bottom: 0 }` 추가, `pre-wrap` 제거.
- **같은 식당/카페가 지점 표기만 다르게 중복 등장**: "강릉샌드 본점"/"강릉샌드",
  "강릉불고기 본점"/"강릉불고기 초당점"처럼 TourAPI에 지점명만 다르게 중복 등록된 경우를
  이름 전체 일치로만 걸러내던 기존 방식이 못 잡던 문제 → 마지막 토큰이 "점"으로 끝나면
  지점명으로 보고 떼어내서 브랜드명만으로 dedup(`_strip_branch_suffix`).
- **숙박이 일반 관광 슬롯에 여러 번 등장하던 문제**: RAG/실검색 후보군이 숙박(content_type_id
  32)을 취향 유사도로 걸러내지 못해 호텔이 오전/오후 등 일반 활동처럼 중복 등장했음 →
  후보군에서 숙박 제외, 선택된 `lodging_place`를 1일차 점심 이후(체크인 시점)에 "체크인"
  일정으로 한 번만 삽입.
- **최근 대화 제목**: 사용자가 친 말 그대로 잘라서 보여주던 것 → 도시+기간으로 요약된
  제목("강릉 1박 2일 여행")으로 표시(`chat_store.update_session_title`).
- **최근 대화 클릭 시 결과 패널(일정/동선/비용) 복원**: 대화 메시지만 복원되고 일정은
  복원 안 되던 문제 → `chat_sessions.last_result`(jsonb) 컬럼 추가(사용자가 Supabase에서
  직접 실행), 매 요청 완료 시 전체 결과를 저장하고 세션 선택 시 복원하도록
  `chat_store.update_session_result`/`get_session_result` 추가.

## 6. 컨텍스트 이어가기(부분 재계획) 구현

기존엔 "카페 말고 맛집으로 바꿔줘", "3일로 늘려줘" 같은 후속 요청이 **조건(도시/기간 등)만
이어받아 처음부터 다시 검색**해서, 이미 확정된 Day1/Day2 장소까지 통째로 다른 곳으로
바뀌는 문제가 있었음. 범위를 좁혀 아래 두 가지를 구현.

### 6-1. 기간 연장 ("3일로 늘려줘")

- `previous_result`(직전 턴 전체 결과: daily_schedule/route_summary 포함)를 새 State
  필드로 추가해 API/UI 전 구간에 배선(`state.py`, `graph/workflow.py`, `agents/coordinator.py`,
  `agents/react_loop.py`, `main.py`, `schemas/request.py`, `ui/gradio_app.py`).
- `route_planner_node`가 같은 도시 + 새 일수 > 기존 일수일 때만 `build_incremental_route_plan`
  (`agents/route_planner.py`)으로 분기 → 기존 Day는 그대로 두고 늘어난 날짜분 슬롯만 새로
  채워서 뒤에 이어붙임(마지막 기존 장소 → 새 첫 장소 연결 동선 포함).
- Financial Agent가 전체 기준으로 비용을 다시 계산할 수 있도록, `daily_schedule` 엔트리에
  `category`/`content_type_id`를 남겨두고(기존엔 없었음) 옛 장소를 복원해서 새 장소와
  합쳐 넘김 — 숙박은 같은 숙소로 간주해 늘어난 박수만큼 실측 요금을 유지.

### 6-2. 특정 슬롯 교체 ("2일차 점심만 바꿔줘")

- Solar 파싱 프롬프트(`core/prompts.py`)에 `target_day`/`target_time_slot` 필드 추가,
  Mock 파서(`services/upstage_client.py`)에도 정규식 기반 fallback 추가("N일차"/"Day N" +
  시간대 키워드 둘 다 있을 때만 채움 — 하나만 있으면 기간 설명과 헷갈릴 수 있어 무시).
- `build_slot_replacement_route_plan`(`agents/route_planner.py`): 지목된 슬롯 하나만
  교체하고, 그 앞뒤 동선(route_summary)만 재계산, 나머지 Day/슬롯은 전혀 손대지 않음.
- 안전장치: 이미 일정에 있는 장소는 후보에서 제외, 숙박(체크인) 슬롯 교체는 이번 범위에서
  제외(경고 남기고 기존 유지), 대체 후보를 못 찾으면 기존 일정 그대로 유지.

**검증**: 기존 75개 + 신규 8개(기간 연장 3개, 슬롯 교체 5개) = pytest 80개 전부 통과.
아직 커밋 전 상태.

## 7. 다른 컴퓨터에서 "최근 대화" 저장 안 되는 문제 (원인 진단, 미해결)

- 같은 계정으로 다른 컴퓨터에서 로컬호스트로 열었더니 로그인은 되는데 "최근 대화"가
  비어있는 증상 발견.
- **원인(추정)**: `chat_store`는 RLS를 우회하는 `service_role` 키(`SUPABASE_SERVICE_KEY`)로만
  접속하는데, `.env`는 git에 안 올라가는 파일이라 새 컴퓨터엔 이 키가 없을 가능성이 큼 →
  키가 없으면 `get_service_client()`가 즉시 `RuntimeError`를 던지지만, `ui/gradio_app.py`의
  `except: pass`가 이 에러를 화면에 안 보여주고 조용히 삼킴.
- **다음 액션**: 새 컴퓨터의 `.env`에 `SUPABASE_URL`/`SUPABASE_KEY`/`SUPABASE_SERVICE_KEY`가
  다 채워져 있는지 확인 필요(`.env.example` 참고). 그래도 안 되면 예외를 임시로 로그에
  노출해서 정확한 원인 재확인.

## 8. Supabase 기반 LangGraph Checkpoint 저장 연결

- `app/graph/checkpointer.py`(신규): `SUPABASE_DB_URL`(REST API용 `SUPABASE_URL`과 별개,
  Postgres 직접 연결 문자열)로 `PostgresSaver` 생성, `graph.compile(checkpointer=...)`로
  연결. `thread_id`(대화 세션 id)를 `coordinator.py`/`react_loop.py`/`main.py`/
  `gradio_app.py`까지 배선.
- **연결 삽질**: pooler 호스트가 순간적으로 DNS 조회 실패하는 걸 실제로 겪어서 재시도
  로직(3회, 2초 간격) 추가. 반복된 인증 실패로 Supabase pooler의 circuit breaker에
  잠긴 적도 있었음 — 비밀번호 리셋 후 해결.
- **실전에서 잡은 버그**: Supabase pooler(6543, transaction 모드)가 psycopg의 prepared
  statement를 지원 안 해서 실제 그래프 실행 시 `DuplicatePreparedStatement` 에러 발생 —
  `prepare_threshold=None`으로 해결. `MemorySaver`(가짜)로만 테스트했으면 못 잡았을 문제.
- 연결 실패 시(설정 안 함/네트워크 문제) 경고만 남기고 체크포인트 없이 기존과 동일하게
  동작(graceful fallback). 실제 Supabase에 체크포인트 행이 쌓이는 것까지 라이브 검증 완료.

## 9. Langfuse 트레이싱 연동

- `app/services/upstage_client.py`: `openai.OpenAI` → `langfuse.openai.OpenAI` 드롭인
  교체 한 줄로 모든 Solar/임베딩 호출이 자동 트레이싱되게 함.
- `app/graph/nodes.py`(4개 노드) + `app/graph/workflow.py`(`run_trip_route_workflow`)에
  `@observe()` 추가 — "요청 하나 = 트레이스 하나"로 묶어서 단계별 소요시간이 보이게 함.
- 실제 Langfuse API로 트레이스 구조까지 직접 조회해서 검증:
  `trip_plan_workflow` → `parse_trip_request`(+ Solar generation) / `route_planner`
  (+ 임베딩) / `financial`(+ usefee 파싱 generation) / `finalize`로 정상 중첩 확인.
- `.env`의 Langfuse 키는 이미 있던 걸 그대로 사용(새 계정 불필요), `auth_check()` 통과.

## 10. UX: 단계별 진행 메시지 + 최종 요약 스트리밍

- `app/graph/workflow.py`: `stream_trip_route_workflow`(신규) — `graph.stream(stream_mode=
  "updates")`로 노드가 끝날 때마다 (진행 메시지, 결과 or None) yield. `coordinator.py`/
  `react_loop.py`에 동일한 스트리밍 wrapper 추가.
- `app/services/upstage_client.py`: `stream_trip_summary`(신규) — 완성된 일정을 Solar
  `stream=True`로 자연어 요약 문단 생성, 조각(delta) 단위로 yield.
- `ui/gradio_app.py`의 `chat()`을 재작성: 로딩 → 4단계 진행 메시지("여행 조건을 분석하고
  있어요...", "관광지와 동선을 찾고 있어요...", "예상 비용을 계산하고 있어요...", "결과를
  정리하고 있어요...") → 결과 패널 확정 후 요약 문단 타이핑 효과 스트리밍 순으로 표시.
  일정/동선/비용 같은 계산된 수치는 스트리밍 대상이 아니라 확정 시 한 번에 표시(요구사항대로).
- 백그라운드 에이전트로 `chat()` 제너레이터 전체(108회 yield)와 서버 부팅을 직접 구동해서
  검증 완료 — 실제 결과 패널은 약 9.6초 시점에 이미 확정되고, 이후 몇 초는 챗봇 말풍선의
  설명 문단이 타이핑되는 구간(체감 속도에 영향, 결과 확인 자체엔 지장 없음).

## 11. 백필 재실행 및 버그 수정

- 중단됐던 백필 4종 재실행: 카테고리 1건, 좌표 29건, 평점 87건, 축제 개최기간 76건.
- 좌표 백필 3건 실패 발견 → 원인 조사 중 버그 2개 확인:
  - `backfill_coordinates`가 `detail.get("title", 대체값)` 문법을 잘못 씀(키가 있는데
    값이 `None`이면 대체값으로 안 떨어짐) → `.get(key) or 대체값`으로 수정
  - `get_places_missing_coordinates`가 애초에 `title`/`address` 컬럼을 안 가져와서
    대체값 자체가 없었음 → 컬럼 추가
  - 수정 후 재실행, 3건 전부 해결(좌표 미해결 0건)
- TourAPI가 완전히 빈 응답(아이템 0개)을 주는 폐업/삭제 콘텐츠 3건(라세느 롯데호텔서울,
  제주한잔 우리술 페스티벌, 전주페스타)은 `places` 테이블에서 삭제.

## 12. CI 실패로 어제부터 배포가 안 되고 있던 문제 발견 및 수정

- 서버 배포 요청 중 GitHub Actions 확인 → **`16b2817`(어제 세션 마지막 커밋)부터 오늘 모든
  커밋까지 CI가 계속 실패**하고 있었고, CD는 매번 자동으로 스킵되고 있었음을 발견. 마지막
  성공 배포는 `e86702d`(7/13 04:05) — 그동안의 작업이 전부 서버에 반영 안 된 상태였음.
- 원인: ruff lint 오류 5건(미사용 변수/import, 대부분 오늘 이전부터 있던 것) — CI의
  "Run Ruff lint" 단계에서 실패해서 뒤 단계(문법 체크/테스트)는 실행조차 안 되고 있었음.
- `app/agents/route_planner.py`/`app/rag/vector_store.py`/`ui/gradio_app.py`에서 미사용
  변수·import 제거. 로컬에서 `uv lock --check`/ruff/`compileall`/pytest 전부 통과 확인
  후 푸시 → CI 통과 → CD 자동 트리거되어 실제 배포 진행.

## 13. 카라반/글램핑/캠핑장이 숙박으로 인식 안 되던 버그 수정

- 카라반을 숙소로 못 잡고 일반 오전 일정에 넣던 문제 제보 → DB 직접 조회로 원인 확인:
  TourAPI가 카라반(5건 전부)/글램핑(7건 전부)/캠핑장(10건 전부)을 `숙박`이 아니라
  `레포츠`로 등록해둠(실제 야영장·캠핑장 카테고리 코드가 그렇게 매핑됨).
- `app/agents/route_planner.py`: `_is_lodging_by_name()` 추가 — 이름에 "카라반"/"글램핑"/
  "캠핑장"이 있으면 category와 무관하게 숙박으로 취급. 일반 관광지 후보 검색에서는
  제외하고, 숙박 전용 검색(`_search_lodging_place`)에서는 후보로 포함. 실제 숙박으로
  확정되면 category/content_type_id를 항상 "숙박"/"32"로 강제(후속 요청에서 다시 찾을
  때 원본 카테고리가 남아있으면 못 찾는 문제 방지).
- RAG 벡터 검색 순위까지 실측 확인: 검색어에 "카라반, 글램핑, 캠핑장" 키워드를 추가하니
  이 장소들이 실제 "숙박" 카테고리 호텔보다도 유사도 순위가 더 높게 나옴.

## 14. 장소 이동 기능 (Step 1: 맞바꾸기 → 이동+백필로 재설계)

- 처음엔 "두 슬롯을 서로 맞바꾸기"로 구현했는데, 사용자 피드백으로 "그냥 하나만 옮기고
  그 자리를 위해 목적지 기존 장소는 빼고, 원래 자리(source)는 새로 검색해서 채우는" 방식이
  더 자연스럽다고 판단 → 전면 재설계.
- `prompts.py`/`upstage_client.py`: `move_source_day`/`move_source_time_slot`/
  `move_destination_day`/`move_destination_time_slot` 필드 추가. Mock 파서에도 "N일차"가
  서로 다르게 두 번 언급되면 이동 요청으로 감지하는 정규식 기반 fallback 추가.
- `build_place_move_route_plan`(`agents/route_planner.py`, 기존 `build_place_swap_route_plan`
  대체): destination 슬롯엔 옮겨온 장소가 들어가고 원래 있던 장소는 제외됨, source 슬롯은
  `build_slot_replacement_route_plan`과 동일한 방식(식사 시간대면 음식점, 아니면 일반
  관광지)으로 새로 검색해서 채움. **source에 채울 후보를 못 찾으면 이동 자체를 취소**하고
  기존 일정을 그대로 유지(destination만 바뀌고 source가 비는 반쪽짜리 상태 방지).
- 테스트 5건 재작성.

## 15. 일차별 조건 (Step 2: "1일차는 바다/카페, 2일차는 액티비티, 마지막날은 여유롭게")

- 범위를 처음 계획할 때만 지원하는 것으로 좁힘(이미 짜인 일정을 후속으로 "2일차만
  액티비티로 바꿔줘"는 별도 기능, 이번 범위 밖). 조건이 지정 안 된 날짜는 전체 공통값 사용.
- `prompts.py`: `daily_preferences` 필드 추가 — "마지막날"은 duration으로 실제 일차
  번호로 환산하도록 지시. Mock 파서는 이 중첩 구조를 규칙 기반으로 못 뽑아내므로 항상
  빈 리스트 반환(자연스럽게 전체 공통 조건으로 대체됨).
- `_build_time_slots`에 `day_intensity_overrides` 파라미터 추가(일차별 다른 일정 강도) —
  오버라이드 없으면 기존과 완전히 동일하게 동작(회귀 위험 0으로 설계).
- `build_route_plan`: `daily_preferences` 없으면 **기존 코드 그대로**, 있으면 날짜별로
  따로 취향 검색(`_search_day_partitioned_candidates`, 신규)해서 날짜 순서대로 이어붙이는
  경로로 분기. 날짜마다 지리적 군집화도 독립 적용(다른 날은 다른 지역이어도 됨), 특정
  날짜 전용 취향으로 슬롯을 못 채우면 전체 공통 취향으로 자동 보충(날짜 정렬 깨짐 방지).
- **통합 테스트가 실제 버그를 잡음**: 오버라이드 경로에서 응답의 `rag_ranked_places` 필드를
  채우는 코드가 `rag_places` 미정의로 `UnboundLocalError` 발생 → 수정.
- 신규 테스트 5건, pytest 94개 통과.

## 16. 숙박/음식점 추천 이유 문구 개선

- "OO 취향에 잘 맞습니다"가 억지로 끼워맞춘 것처럼 읽힌다는 피드백 → 음식점은 "리뷰
  686개, 평점 4.2의 인기 맛집입니다.", 숙박은 "편하게 쉬기 좋은 숙소입니다."처럼 평점/
  리뷰수 기반 자연스러운 설명으로 변경(`_build_place_reason`). 다른 카테고리(관광지 등)는
  기존 문구 유지. 테스트 1건 추가, pytest 95개 통과.

---

## 참고: 오늘 커밋/브랜치 정리
- `feature/ui-redesign`, `feature/rag-coordinates` → `main`에 병합 및 푸시 완료
  (`10258ec`, `7b6d09c`, `0bbbec4`).
- `feature/ui-ux-improvements`는 커밋된 변경사항이 없어 병합 대상 없음.
- 항목 1~5는 `16b2817`, 항목 6(컨텍스트 이어가기)은 `1009afc`로 각각
  `feature/agent-performance`에서 `main`에 병합/푸시 완료.
- 항목 8(체크포인트) + 백필 버그 수정은 `feature/langgraph-checkpoint`에서 `main`으로 병합.
- 항목 9(Langfuse)는 `feature/langfuse`, 항목 10(스트리밍)은 `feature/streaming-ux`에서
  각각 `main`으로 병합.
- 항목 12(CI 수정)는 `main`에 직접 커밋 후 푸시.
- 배포 서버: `http://34.50.22.20:8000/` (GCE VM, GHCR 이미지 기반 Docker Compose).
- 항목 13~16(카라반 버그, 장소 이동 재설계, 일차별 조건, 추천 이유 문구)은
  `feature/performance-tuning` 브랜치에서 작업, 아직 커밋 전 상태.
