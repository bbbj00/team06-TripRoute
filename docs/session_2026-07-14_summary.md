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

---

## 참고: 오늘 커밋/브랜치 정리
- `feature/ui-redesign`, `feature/rag-coordinates` → `main`에 병합 및 푸시 완료
  (`10258ec`, `7b6d09c`, `0bbbec4`).
- `feature/ui-ux-improvements`는 커밋된 변경사항이 없어 병합 대상 없음.
- 항목 1~5는 `16b2817`로 커밋되어 `feature/agent-performance` → `main`에 병합/푸시 완료.
- 항목 6(컨텍스트 이어가기)은 아직 커밋 전 상태.
