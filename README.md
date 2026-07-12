# TripRoute

> 여행 도시와 취향을 자연어로 입력하고 이동수단을 선택하면, 공공데이터·이동정보 API·RAG·LLM Agent를 활용해 시간대별 여행 일정표, 동선 메모, 예상 비용을 자동 생성하는 Agentic Workflow 프로젝트입니다. 로컬 실행 확인은 중간 단계일 뿐, **완성된 Agent를 Docker로 컨테이너화하고 CI/CD 파이프라인을 구성해서, 실제로 동작하는 서비스로 GCP에 배포하는 것**이 최종 목적입니다 (세부 서비스는 추후 결정 — Cloud Run 유력).

---

## 1. 프로젝트 개요

TripRoute는 사용자가 여행하고 싶은 도시, 날짜, 기간, 여행 스타일을 자연어로 입력하고 이동수단을 체크박스로 선택하면, 관광지 정보와 이동 정보를 기반으로 현실적인 여행 일정을 자동으로 생성하는 AI 여행 코스 설계 서비스입니다.

단순히 관광지를 나열하는 것이 아니라, 다음 요소를 함께 고려합니다.

* 사용자의 여행 취향
* 여행 도시 및 계절
* 관광지 간 연관성
* 장소 간 이동 거리와 소요시간
* 이동수단별 예상 비용
* 하루 일정의 현실성
* 예상 식비, 교통비, 입장료, 숙박비

본 프로젝트는 실제 상용 여행 예약 서비스가 아니라, **완성된 Agent를 패키징해서 GCP에 실제로 동작하는 서비스로 배포하는 Agentic Workflow MVP**를 목표로 합니다.

---

## 2. 프로젝트 목표

### 2-1. 핵심 목표

여행 계획 과정에서 사용자가 직접 검색해야 하는 과정을 줄이고, AI Agent가 다음 정보를 자동으로 구성하도록 합니다.

1. 여행 조건 분석
2. 관광지 후보 검색
3. 취향 기반 관광지 추천
4. 연관 관광지 탐색
5. 이동 동선 설계
6. 시간대별 일정표 생성
7. 이동수단별 예상 비용 계산
8. 최종 여행 플랜 출력

### 2-2. 해결하려는 문제

여행 계획을 세울 때 사용자는 다음과 같은 어려움을 겪습니다.

* 관광지를 하나씩 검색해야 해서 시간이 오래 걸림
* 처음 방문하는 지역의 지리적 감각이 부족함
* 어떤 장소를 먼저 방문해야 할지 판단하기 어려움
* 장소 간 이동 시간이 일정에 반영되지 않음
* 여행 스타일과 계절 조건을 함께 고려하기 어려움
* 예상 비용을 따로 계산해야 함

TripRoute는 이러한 문제를 해결하기 위해 **장소 추천 + 방문 순서 추천 + 시간대별 일정표 + 예상 비용 계산**을 하나의 흐름으로 제공합니다.

---

## 3. 주요 사용자

TripRoute의 주요 대상 사용자는 다음과 같습니다.

### 3-1. 효율적인 여행을 원하는 20대 대학생 및 사회초년생

* 시간과 비용을 모두 고려해야 함
* 친구들과 짧은 기간 여행을 계획하는 경우가 많음
* 이동 동선과 예상 비용에 민감함

### 3-2. 여행 계획이 익숙하지 않은 초보 여행자

* 자유여행 경험이 적음
* 어떤 순서로 계획을 세워야 하는지 모름
* 추천 일정표가 있으면 그대로 참고하기 좋음

### 3-3. 낯선 지역을 처음 방문하는 초행 여행자

* 해당 지역의 거리감과 교통 특성을 모름
* 관광지 간 위치 관계를 파악하기 어려움
* 이동이 자연스러운 코스가 필요함

### 3-4. 계획 수립을 귀찮아하는 직장인 유저

* 퇴근 후 맛집, 카페, 관광지를 하나씩 비교하기 부담스러움
* 빠르게 참고 가능한 일정 초안이 필요함
* 너무 빡빡하지 않은 현실적인 일정을 선호함

---

## 4. 핵심 기능

| 기능           | 설명                                  |
| ------------ | ----------------------------------- |
| 자연어 여행 조건 입력 | 사용자가 도시, 날짜, 기간, 취향, 일정 강도를 자연어로 입력 |
| 이동수단 선택      | 자차, 렌터카, 대중교통, 택시 중 선택              |
| 인원수 입력       | 비용 계산을 위해 여행 인원수 입력                 |
| 관광지 후보 조회    | 한국관광공사 TourAPI 기반 관광지 정보 조회         |
| 취향 기반 RAG 검색 | 관광지 설명을 임베딩하고 사용자 취향과 유사한 장소 검색     |
| 연관 관광지 조회    | 함께 방문하기 좋은 관광지 후보 탐색                |
| 동선 설계        | 카카오모빌리티 API 기반 장소 간 거리와 이동시간 반영     |
| 일정표 생성       | 시간대별 여행 일정표 생성                      |
| 예상 비용 계산     | 교통비, 식비, 입장료, 숙박비 등 예상 비용 산정        |
| 주의사항 출력      | 대중교통 추정치, 실시간 정보 미반영 등 한계 안내        |

---

## 5. 사용자 입력 예시

```text
강릉으로 1박 2일 여행 가고 싶어.
날짜는 8월이고, 바다랑 감성 카페, 먹거리를 좋아해.
너무 빡세지 않고 동선이 자연스럽게 짜줘.
```

추가 UI 입력값:

```text
이동수단: 대중교통
인원수: 2명
```

---

## 6. 예상 출력 예시

### 6-1. 조건 요약

```text
여행지: 강릉
기간: 1박 2일
계절: 여름
여행 스타일: 바다, 감성 카페, 먹거리
이동수단: 대중교통
인원수: 2명
일정 강도: 여유로운 일정
```

### 6-2. 일정표 예시

| Day   | 시간대 | 장소       | 추천 이유                    | 동선 메모            |
| ----- | --- | -------- | ------------------------ | ---------------- |
| Day 1 | 오전  | 안목해변     | 강릉 바다 분위기를 느낄 수 있는 대표 장소 | 여행 시작점으로 적합      |
| Day 1 | 점심  | 강릉 중앙시장  | 먹거리 여행 취향 반영             | 시내권 식사 코스로 배치    |
| Day 1 | 오후  | 안목 커피거리  | 감성 카페 선호 반영              | 안목해변과 함께 방문하기 좋음 |
| Day 1 | 저녁  | 경포호/경포해변 | 여름 저녁 산책 코스로 적합          | 낮보다 부담 적은 야외 일정  |
| Day 2 | 오전  | 오죽헌      | 역사문화 관광지                 | 전날 바다 중심 일정과 균형  |
| Day 2 | 오후  | 주문진      | 여행 마무리 코스                | 남은 시간에 따라 선택 가능  |

### 6-3. 예상 비용 예시

| 항목      |    예상 비용 | 설명                      |
| ------- | -------: | ----------------------- |
| 교통비     |  12,000원 | 대중교통 거리 기반 휴리스틱 추정      |
| 식비      |  60,000원 | 2인 기준 평균 식비             |
| 카페/간식비  |  30,000원 | 감성 카페 방문 기준             |
| 입장료     |  10,000원 | TourAPI usefee 정보 기반 추정 |
| 숙박비     | 100,000원 | 1박 평균 숙박비               |
| 총 예상 비용 | 212,000원 | 참고용 예상 비용               |

> 대중교통 이동시간과 요금은 실시간 환승 경로 API를 사용하지 않기 때문에 실제 값이 아닌 거리 기반 추정치입니다.

---

## 7. 시스템 아키텍처

TripRoute는 사용자의 자연어 입력과 이동수단 선택값을 기반으로, Coordinator Agent가 전체 흐름을 제어하고 Route Planner Agent와 Financial Agent가 각각 동선 설계와 예산 산정을 담당하는 Agentic Workflow 구조로 동작합니다.

전체 시스템은 Gradio UI, FastAPI Server, LangGraph Workflow, Supabase, 외부 API, Upstage Solar API를 중심으로 구성됩니다.

```text
[사용자]
   ↓ (자연어 입력 + 이동수단 체크박스 + 인원수 입력)
[Gradio UI]
   ↓
[FastAPI Server]
   ↓
[Coordinator Agent] ←→ [Supabase: pgvector 검색 · Checkpoint 저장]
   ↓ (디스패치)          ↑ (결과 합류, 양방향)
 ┌──────────────────────────────────────────────┐
 │                                              │
[Route Planner Agent]                    [Financial Agent]
 │  ↓ TourAPI / 연관 관광지 / 카카오 API          │  ↓ TourAPI(usefee)
 │  (거리·시간·택시요금 → State 기록) ─────────→ │  (State에서 이동정보를 읽어 정산)
 └──────────────────────────────────────────────┘
   ↓
[Coordinator Agent: 최종 마스터 플랜 조립]
   ↓
[일정표 + 동선 메모 + 예상 비용 출력]
   ↓
[사용자에게 응답]
```

### 7-1. 아키텍처 구성 요소

| 구성 요소               | 역할                                                         |
| ------------------- | ---------------------------------------------------------- |
| 사용자                 | 여행 도시, 날짜, 기간, 취향, 일정 강도 등을 자연어로 입력하고 이동수단과 인원수를 선택        |
| Gradio UI           | 로컬 데모용 입력/출력 화면 제공                                         |
| FastAPI Server      | 사용자 요청을 받아 LangGraph Workflow를 실행하는 백엔드 서버                 |
| Coordinator Agent   | 자연어 입력 분석, 여행 조건 추출, RAG 검색 요청, 하위 Agent 호출, 최종 결과 조립      |
| Route Planner Agent | 관광지 후보 조회, 취향 기반 장소 추천, 연관 관광지 탐색, 구간별 이동시간 계산, 일정표 생성     |
| Financial Agent     | 입장료, 교통비, 식비, 숙박비 등 예상 비용 계산                               |
| Supabase            | 관광지 설명 임베딩 저장, pgvector 기반 유사도 검색, LangGraph Checkpoint 저장 |
| Upstage Solar API   | 자연어 분석, 일정 생성, 추천 이유 생성, 비정형 요금 텍스트 구조화                    |
| TourAPI             | 관광지명, 주소, 좌표, 개요, 운영시간, 이용요금 등 관광 정보 제공                    |
| 연관 관광지 API          | 함께 방문하기 좋은 관광지 후보 탐색                                       |
| 카카오모빌리티 API         | 자동차 기준 거리, 소요시간, 예상 택시요금, 통행료 조회                           |
| LangGraph State     | Agent 간 중간 결과를 공유하는 공통 데이터 저장 구조                           |

### 7-2. 데이터 흐름

TripRoute의 전체 데이터 흐름은 다음과 같습니다.

```text
1. 사용자가 여행 조건을 입력한다.
   예: "강릉으로 1박 2일 여행 가고 싶어. 바다랑 감성 카페를 좋아해."

2. Gradio UI가 자연어 입력, 이동수단, 인원수를 FastAPI Server로 전달한다.

3. FastAPI Server가 LangGraph Workflow를 실행한다.

4. Coordinator Agent가 사용자 입력을 분석한다.
   - 여행 도시
   - 여행 날짜 및 계절
   - 여행 기간
   - 여행 스타일
   - 일정 강도
   - 이동수단
   - 인원수

5. Coordinator Agent가 Supabase pgvector를 통해 취향 기반 RAG 검색을 수행한다.
   - 관광지 설명 벡터와 사용자 취향 벡터를 비교
   - 취향과 유사한 관광지 후보를 추출

6. Route Planner Agent가 관광지와 동선 정보를 구성한다.
   - TourAPI로 관광지 기본 정보 조회
   - 연관 관광지 API로 함께 방문하기 좋은 장소 탐색
   - 카카오모빌리티 API로 구간별 거리와 이동시간 조회
   - 일정 강도와 계절 조건을 반영해 시간대별 일정표 구성

7. Route Planner Agent가 계산한 이동 정보를 LangGraph State에 저장한다.
   - 장소 간 거리
   - 자동차 기준 소요시간
   - 예상 택시요금
   - 통행료
   - 동선 메모

8. Financial Agent가 State에 저장된 이동 정보를 읽어 예상 비용을 계산한다.
   - 이동수단별 교통비 계산
   - 입장료 및 이용요금 파싱
   - 식비, 카페비, 숙박비 추정
   - 총 예상 비용 계산

9. Coordinator Agent가 State에 누적된 결과를 종합한다.
   - 조건 요약
   - 시간대별 일정표
   - 장소별 추천 이유
   - 동선 메모
   - 예상 비용
   - 주의사항

10. 최종 여행 플랜을 사용자에게 출력한다.
```

### 7-3. Agent 간 State 공유 구조

TripRoute는 Agent들이 서로 직접 값을 주고받기보다, LangGraph State를 중심으로 데이터를 공유합니다.

```text
[Coordinator Agent]
   ↓ 사용자 조건 추출
[TripRouteState]
   ↓ 관광지 후보 / 취향 검색 결과 저장
[Route Planner Agent]
   ↓ 동선 / 거리 / 시간 / 택시비 저장
[TripRouteState]
   ↓ 이동정보 / 관광지 요금 읽기
[Financial Agent]
   ↓ 예상 비용 저장
[TripRouteState]
   ↓ 전체 결과 조립
[Coordinator Agent]
```

이 구조를 사용하면 각 Agent의 역할을 명확히 분리할 수 있고, 중간 결과를 재사용하기 쉽습니다. 예를 들어 사용자가 “더 여유롭게 짜줘”라고 추가 요청하면, 기존 관광지 후보와 이동정보를 유지한 채 일정 강도와 시간표만 일부 재구성할 수 있습니다.

### 7-4. 핵심 설계 포인트

#### 1. Coordinator Agent가 전체 흐름을 제어

Coordinator Agent는 단순히 답변을 생성하는 Agent가 아니라, 사용자 입력을 분석하고 필요한 Agent를 호출한 뒤 최종 여행 플랜을 조립하는 중심 역할을 수행합니다.

#### 2. Route Planner Agent와 Financial Agent는 State를 통해 연결

Route Planner Agent가 카카오모빌리티 API로 얻은 거리, 이동시간, 택시비, 통행료 정보를 LangGraph State에 저장하면, Financial Agent는 이 값을 읽어 교통비와 전체 예산을 계산합니다.

즉, 두 Agent가 직접 강하게 결합되어 있는 것이 아니라, State를 매개로 간접 연결됩니다.

#### 3. Supabase는 RAG와 Checkpoint 저장소 역할을 함께 수행

Supabase는 단순한 데이터 저장소가 아니라 두 가지 역할을 가집니다.

| 역할            | 설명                                   |
| ------------- | ------------------------------------ |
| pgvector 검색   | 관광지 설명 임베딩을 저장하고 사용자 취향과 유사한 관광지를 검색 |
| Checkpoint 저장 | LangGraph 실행 중 대화 상태와 중간 결과를 저장      |

#### 4. Upstage Solar API는 모든 Agent가 공용으로 사용

세 Agent는 필요에 따라 Upstage Solar API를 호출합니다.

| Agent               | Upstage 활용 방식              |
| ------------------- | -------------------------- |
| Coordinator Agent   | 자연어 입력 분석, 조건 추출, 최종 응답 생성 |
| Route Planner Agent | 장소 추천 이유 생성, 일정표 문장화       |
| Financial Agent     | 비정형 이용요금 텍스트 구조화, 비용 설명 생성 |

#### 5. 대중교통은 실측이 아니라 휴리스틱 추정

카카오모빌리티 API는 자동차 기준 거리, 소요시간, 택시비, 통행료를 제공하지만 대중교통 환승 경로와 요금은 제공하지 않습니다.

따라서 MVP에서는 대중교통을 다음 방식으로 처리합니다.

```text
대중교통 예상 소요시간 = 자동차 기준 소요시간 × 1.5 ~ 2.0
대중교통 예상 요금 = 거리 기반 기본요금 + 초과 거리 가산
```

최종 출력에는 반드시 다음과 같은 안내 문구를 포함합니다.

```text
대중교통 시간과 비용은 실시간 환승 경로가 아닌 거리 기반 참고용 추정치입니다.
```

#### 6. 지도 시각화와 실시간 재최적화는 MVP에서 제외

TripRoute의 MVP는 지도 위 경로 시각화나 실시간 교통 재계산이 아니라, 로컬 환경에서 Agent들이 협업해 여행 일정과 예상 비용을 생성하는 데 초점을 둡니다.

따라서 지도 렌더링, 실시간 대중교통 경로, 예약/결제 기능은 MVP 범위에서 제외합니다.

---

## 8. Agent 설계

TripRoute는 LangGraph 기반의 Agentic Workflow 구조로 동작합니다.

### 8-1. Coordinator Agent

사용자 입력을 분석하고 전체 흐름을 조정하는 Agent입니다.

주요 역할:

* 자연어 입력 분석
* 도시, 날짜, 기간, 취향, 일정 강도 추출
* 이동수단 체크박스 값 결합
* 인원수 입력값 결합
* RAG 검색 요청
* Route Planner Agent 호출
* Financial Agent 호출
* 최종 여행 플랜 조립
* 사용자에게 결과 출력

### 8-2. Route Planner Agent

관광지 추천과 동선 설계를 담당하는 Agent입니다.

주요 역할:

* TourAPI 기반 관광지 후보 조회
* Supabase pgvector 기반 취향 유사도 검색
* 연관 관광지 API 기반 함께 방문하기 좋은 장소 탐색
* 카카오모빌리티 API 기반 구간별 거리와 이동시간 조회
* 일정 과밀도 체크
* 계절과 여행 스타일을 반영한 시간대별 일정 구성

### 8-3. Financial Agent

예상 비용 계산을 담당하는 Agent입니다.

주요 역할:

* TourAPI의 usefee 비정형 요금 텍스트 파싱
* 이동수단별 교통비 계산
* 카카오모빌리티 API의 택시비, 통행료 정보 활용
* 대중교통 비용 휴리스틱 계산
* 식비, 카페비, 숙박비 등 평균 비용 추정
* 최종 비용 요약 생성

---

## 9. LangGraph State 설계

TripRoute의 각 Agent는 공통 State를 통해 데이터를 주고받습니다.

Coordinator Agent가 사용자 입력을 분석해 State에 저장하고, Route Planner Agent가 관광지와 동선 정보를 추가합니다. 이후 Financial Agent가 비용 정보를 추가하고, 마지막으로 Coordinator Agent가 State 전체를 바탕으로 최종 응답을 생성합니다.

```python
from typing import TypedDict, List, Dict, Any


class TripRouteState(TypedDict):
    user_input: str
    city: str
    season: str
    duration: str
    travel_style: List[str]
    transport_mode: str
    people_count: int

    candidate_places: List[Dict[str, Any]]
    rag_ranked_places: List[Dict[str, Any]]
    related_places: List[Dict[str, Any]]
    route_segments: List[Dict[str, Any]]

    daily_schedule: List[Dict[str, Any]]
    cost_summary: Dict[str, Any]
    warnings: List[str]
```

### 9-1. State 필드 설명

| 필드                  | 설명                           |
| ------------------- | ---------------------------- |
| `user_input`        | 사용자의 원문 자연어 입력               |
| `city`              | 여행 도시                        |
| `season`            | 날짜 기반 계절 정보                  |
| `duration`          | 여행 기간                        |
| `travel_style`      | 여행 취향 리스트                    |
| `transport_mode`    | 체크박스로 선택한 이동수단               |
| `people_count`      | 여행 인원수                       |
| `candidate_places`  | TourAPI 기반 관광지 후보            |
| `rag_ranked_places` | RAG 유사도 검색 결과                |
| `related_places`    | 연관 관광지 API 기반 후보             |
| `route_segments`    | 장소 간 거리, 소요시간, 택시비, 통행료 정보   |
| `daily_schedule`    | 시간대별 일정표                     |
| `cost_summary`      | 예상 비용 요약                     |
| `warnings`          | 추정치, API 실패, 휴무일 불확실성 등 주의사항 |

---

## 10. 기술 스택

| 구분                | 기술                      | 활용 목적                    |
| ----------------- | ----------------------- | ------------------------ |
| Language          | Python                  | 전체 Agent 로직 및 API 호출     |
| Backend           | FastAPI                 | Agent 실행 API 서버          |
| UI                | Gradio                  | 로컬 데모 화면                 |
| Agent Framework   | LangGraph               | Agent 흐름 및 State 관리      |
| LLM               | Upstage Solar API       | 입력 분석, 일정 생성, 추천 이유 생성   |
| Embedding         | Upstage Solar Embedding | 관광지 설명 벡터화               |
| Vector DB         | Supabase pgvector       | RAG 기반 유사 관광지 검색         |
| Public Data API   | 한국관광공사 TourAPI          | 관광지 기본 정보 조회             |
| Related Place API | 관광지별 연관 관광지 정보          | 함께 방문하기 좋은 관광지 탐색        |
| Mobility API      | 카카오모빌리티 길찾기 API         | 거리, 이동시간, 택시비, 통행료 조회    |
| Cache             | JSON / CSV              | API 결과 캐싱 및 fallback 데이터 |
| Observability     | Langfuse                | Agent 실행 흐름 추적           |
| Version Control   | GitHub                  | 팀 협업 및 코드 관리             |

---

## 11. 프로젝트 폴더 구조

```text
team06-TripRoute/
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── state.py
│   │   └── prompts.py
│   │
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── workflow.py
│   │   ├── nodes.py
│   │   └── edges.py
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── coordinator.py
│   │   ├── route_planner.py
│   │   └── financial.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── upstage_client.py
│   │   ├── tour_api.py
│   │   ├── related_place_api.py
│   │   ├── kakao_mobility.py
│   │   └── supabase_client.py
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── embedder.py
│   │   ├── vector_store.py
│   │   └── retriever.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cache.py
│   │   ├── formatter.py
│   │   ├── cost_rules.py
│   │   └── transport_rules.py
│   │
│   └── schemas/
│       ├── __init__.py
│       ├── request.py
│       ├── response.py
│       └── place.py
│
├── ui/
│   └── gradio_app.py
│
├── data/
│   ├── raw/
│   ├── cache/
│   └── sample/
│       ├── sample_places.json
│       ├── sample_routes.json
│       └── sample_plan.json
│
├── docs/
│   ├── project_plan.md
│   ├── architecture.md
│   ├── api_notes.md
│   └── state_design.md
│
└── tests/
    ├── test_route_planner.py
    ├── test_financial.py
    └── test_rag.py
```

---

## 12. 폴더별 역할

### 12-1. `app/main.py`

FastAPI 서버 실행 파일입니다.

주요 역할:

* `/trip/plan` 엔드포인트 제공
* 사용자 요청 수신
* LangGraph Workflow 실행
* 최종 여행 플랜 반환

### 12-2. `app/core/`

프로젝트 공통 설정과 State, Prompt를 관리합니다.

| 파일           | 역할                  |
| ------------ | ------------------- |
| `config.py`  | `.env` 환경변수 로드      |
| `state.py`   | `TripRouteState` 정의 |
| `prompts.py` | Agent별 프롬프트 관리      |

### 12-3. `app/graph/`

LangGraph Workflow를 구성합니다.

| 파일            | 역할                  |
| ------------- | ------------------- |
| `workflow.py` | 전체 그래프 생성           |
| `nodes.py`    | Agent 노드 정의         |
| `edges.py`    | Agent 실행 순서 및 조건 정의 |

### 12-4. `app/agents/`

Agent의 핵심 로직을 구현합니다.

| 파일                 | 역할               |
| ------------------ | ---------------- |
| `coordinator.py`   | 입력 분석 및 최종 응답 조립 |
| `route_planner.py` | 관광지 추천 및 동선 설계   |
| `financial.py`     | 예상 비용 계산         |

### 12-5. `app/services/`

외부 API 호출을 담당합니다.

| 파일                     | 역할                             |
| ---------------------- | ------------------------------ |
| `upstage_client.py`    | Upstage LLM 및 Embedding API 호출 |
| `tour_api.py`          | 한국관광공사 TourAPI 호출              |
| `related_place_api.py` | 연관 관광지 API 호출                  |
| `kakao_mobility.py`    | 카카오모빌리티 길찾기 API 호출             |
| `supabase_client.py`   | Supabase 연결 관리                 |

### 12-6. `app/rag/`

RAG 관련 기능을 담당합니다.

| 파일                | 역할                        |
| ----------------- | ------------------------- |
| `embedder.py`     | 관광지 설명 임베딩 생성             |
| `vector_store.py` | Supabase pgvector 저장 및 검색 |
| `retriever.py`    | 사용자 취향 기반 유사 관광지 검색       |

### 12-7. `app/utils/`

보조 로직을 관리합니다.

| 파일                   | 역할                 |
| -------------------- | ------------------ |
| `cache.py`           | API 응답 캐싱          |
| `formatter.py`       | 최종 출력 포맷 변환        |
| `cost_rules.py`      | 식비, 숙박비, 입장료 추정 규칙 |
| `transport_rules.py` | 대중교통 시간/요금 휴리스틱    |

### 12-8. `ui/`

Gradio 기반 로컬 데모 UI를 구현합니다.

주요 입력 요소:

* 자연어 여행 조건 입력창
* 이동수단 선택
* 인원수 입력
* 일정 생성 버튼
* 결과 출력 영역

### 12-9. `data/`

API 응답 데이터와 fallback 샘플 데이터를 저장합니다.

| 폴더        | 역할                  |
| --------- | ------------------- |
| `raw/`    | 원본 API 응답 저장        |
| `cache/`  | API 호출 결과 캐시        |
| `sample/` | API 실패 시 사용할 샘플 데이터 |

### 12-10. `docs/`

기획 및 설계 문서를 저장합니다.

| 파일                | 역할                    |
| ----------------- | --------------------- |
| `project_plan.md` | 프로젝트 전체 기획서           |
| `architecture.md` | 시스템 아키텍처 설명           |
| `api_notes.md`    | API 사용 범위와 한계 정리      |
| `state_design.md` | LangGraph State 구조 설명 |

---

## 13. 설치 및 실행 방법

### 13-1. 저장소 클론

```bash
git clone https://github.com/bbbj00/team06-TripRoute.git
cd team06-TripRoute
```

### 13-2. 가상환경 생성

Windows PowerShell 기준:

```bash
python -m venv .venv
.venv\Scripts\activate
```

macOS / Linux 기준:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 13-3. 패키지 설치

```bash
pip install -r requirements.txt
```

### 13-4. 환경변수 설정

`.env.example` 파일을 복사해 `.env` 파일을 생성합니다.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS / Linux:

```bash
cp .env.example .env
```

`.env` 파일에 실제 API Key를 입력합니다.

```env
UPSTAGE_API_KEY=your_upstage_api_key
TOUR_API_KEY=your_tour_api_key
KAKAO_MOBILITY_API_KEY=your_kakao_mobility_api_key

SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_HOST=https://cloud.langfuse.com
```

---

## 14. 실행 방법

### 14-1. FastAPI 서버 실행

```bash
uvicorn app.main:app --reload
```

실행 후 아래 주소에서 API 문서를 확인할 수 있습니다.

```text
http://localhost:8000/docs
```

### 14-2. Gradio UI 실행

```bash
python ui/gradio_app.py
```

실행 후 터미널에 표시되는 로컬 주소로 접속합니다.

예시:

```text
http://127.0.0.1:7860
```

---

## 15. API 요청 예시

### POST `/trip/plan`

요청 예시:

```json
{
  "user_input": "강릉으로 1박 2일 여행 가고 싶어. 날짜는 8월이고, 바다랑 감성 카페, 먹거리를 좋아해. 너무 빡세지 않고 동선이 자연스럽게 짜줘.",
  "transport_mode": "대중교통",
  "people_count": 2
}
```

응답 예시:

```json
{
  "condition_summary": {
    "city": "강릉",
    "season": "여름",
    "duration": "1박 2일",
    "travel_style": ["바다", "감성 카페", "먹거리"],
    "transport_mode": "대중교통",
    "people_count": 2
  },
  "daily_schedule": [
    {
      "day": "Day 1",
      "time": "오전",
      "place": "안목해변",
      "reason": "강릉 바다 분위기를 느낄 수 있는 대표 장소입니다.",
      "route_note": "여행 시작점으로 적합합니다."
    }
  ],
  "cost_summary": {
    "transport": 12000,
    "food": 60000,
    "cafe": 30000,
    "lodging": 100000,
    "total": 202000
  },
  "warnings": [
    "대중교통 시간과 요금은 실시간 환승 경로가 아닌 거리 기반 추정치입니다."
  ]
}
```

---

## 16. RAG 설계

TripRoute의 RAG는 환각 방지가 아니라 **사용자 취향과 관광지 설명 간 의미적 매칭**을 정교화하기 위해 사용합니다.

### 16-1. RAG 처리 흐름

```text
TourAPI 관광지 설명 수집
        ↓
Upstage Solar Embedding으로 관광지 설명 벡터화
        ↓
Supabase pgvector에 저장
        ↓
사용자 취향 문장 임베딩
        ↓
관광지 설명 벡터와 유사도 검색
        ↓
취향에 맞는 관광지 후보 반환
```

### 16-2. RAG 검색 예시

사용자 입력:

```text
바다랑 감성 카페, 먹거리를 좋아해
```

RAG 검색 결과 예시:

```text
1. 안목해변
2. 안목 커피거리
3. 강릉 중앙시장
4. 경포해변
5. 주문진
```

이후 Route Planner Agent는 RAG 결과만 사용하는 것이 아니라, 다음 정보를 함께 고려합니다.

* RAG 유사도 점수
* 연관 관광지 순위
* 장소 간 이동시간
* 계절 조건
* 일정 강도
* 관광지 운영시간 및 휴무일

---

## 17. 이동수단별 비용 계산 방식

TripRoute는 이동수단에 따라 비용 계산 방식을 다르게 적용합니다.

| 이동수단 | 계산 방식                         |
| ---- | ----------------------------- |
| 자차   | 카카오모빌리티 API의 거리, 소요시간, 통행료 활용 |
| 렌터카  | 자차 기준 이동 정보 + 렌터카 비용 추정       |
| 택시   | 카카오모빌리티 API의 예상 택시요금 활용       |
| 대중교통 | 자동차 기준 거리/시간을 바탕으로 자체 휴리스틱 추정 |

### 17-1. 대중교통 휴리스틱

대중교통은 MVP에서 별도 실시간 대중교통 라우팅 API를 사용하지 않습니다.

따라서 다음 방식으로 추정합니다.

```text
대중교통 예상 소요시간 = 자동차 기준 소요시간 × 1.5 ~ 2.0
대중교통 예상 요금 = 거리 기반 기본요금 + 초과 거리 가산
```

주의사항:

```text
대중교통 결과는 실제 환승 경로, 배차 간격, 도보 이동, 지역별 교통 체계를 완전히 반영하지 않습니다.
따라서 결과 화면에는 참고용 추정치임을 명시합니다.
```

---

## 18. MVP 범위

### 18-1. MVP에 포함되는 기능

* 자연어 여행 조건 입력
* 이동수단 선택
* 인원수 입력
* 관광지 후보 조회
* RAG 기반 취향 매칭
* 카카오모빌리티 기반 자동차 기준 거리/시간 조회
* 대중교통 휴리스틱 추정
* 시간대별 일정표 생성
* 예상 비용 출력
* Gradio 기반 로컬 UI
* FastAPI 기반 실행 엔드포인트

### 18-2. MVP에서 제외되는 기능

* 실제 숙소 예약
* 식당 예약
* 결제/예매
* 실시간 교통상황 반영
* 실시간 대중교통 환승 경로 조회
* 지도 위 경로 시각화
* 사용자 로그인
* 장기 개인화 추천
* 모바일 앱 배포

---

## 19. 개발 로드맵

### Step 1. 프로젝트 기본 구조 구성

* GitHub 저장소 세팅
* 폴더 구조 생성
* `.env.example`, `.gitignore`, `requirements.txt` 작성
* FastAPI 기본 서버 실행 확인
* Gradio 기본 UI 실행 확인

### Step 2. 외부 API 연결 테스트

* TourAPI 관광지 검색 테스트
* 카카오모빌리티 길찾기 API 테스트
* Upstage Solar API 테스트
* Supabase 연결 테스트

### Step 3. State 및 Agent 기본 흐름 구현

* `TripRouteState` 정의
* Coordinator Agent 입력 파싱 구현
* Route Planner Agent 기본 장소 후보 생성
* Financial Agent 기본 비용 계산
* LangGraph Workflow 연결

### Step 4. RAG 구현

* 관광지 설명 수집
* Upstage Embedding 호출
* Supabase pgvector 저장
* 사용자 취향 기반 유사도 검색
* RAG 결과를 Route Planner에 연결

### Step 5. 동선 및 비용 계산 고도화

* 장소 간 이동시간 계산
* 하루 일정 과밀도 체크
* 이동수단별 비용 분기
* 대중교통 휴리스틱 적용
* usefee 텍스트 파싱

### Step 6. 최종 출력 포맷 구성

* 조건 요약
* 시간대별 일정표
* 장소별 추천 이유
* 동선 메모
* 예상 비용표
* 주의사항 출력

### Step 7. 시연 준비

* 샘플 데이터 준비
* API 실패 fallback 처리
* README 정리
* 발표용 아키텍처 다이어그램 준비
* 실행 화면 캡처

### Step 8. Docker 컨테이너화 및 CI/CD 기반 GCP 배포

* 배포 대상 서비스 확정 (Cloud Run 유력 — FastAPI를 컨테이너로 띄우고 Gradio도 같은 서비스 또는 별도 서비스로 서빙)
* `Dockerfile` 작성 및 로컬 컨테이너 실행 확인
* `.env`의 API Key/Secret을 GCP Secret Manager(또는 Cloud Run 환경변수)로 이관
* CI/CD 파이프라인 구성 (예: GitHub Actions → 컨테이너 이미지 빌드 → Artifact Registry push → Cloud Run 배포 자동화)
* Cloud Run 배포 및 외부 접속 URL로 최종 시연 확인

---

## 20. 프로젝트 실행 시 주의사항

### 20-1. API Key 관리

`.env` 파일에는 실제 API Key가 들어가므로 GitHub에 올리면 안 됩니다.

반드시 `.gitignore`에 다음 항목이 포함되어야 합니다.

```gitignore
.env
```

공유용으로는 `.env.example`만 업로드합니다.

### 20-2. 캐시 데이터 관리

API 호출 제한이나 시연 중 API 장애를 대비해 캐시와 샘플 데이터를 유지합니다.

* `data/cache/`: 실제 API 호출 결과 캐시
* `data/sample/`: API 실패 시 사용하는 샘플 응답

단, 캐시 데이터에 민감정보가 포함되지 않도록 주의합니다.

### 20-3. 대중교통 결과 한계

대중교통 비용과 시간은 정확한 실시간 경로 탐색 결과가 아닙니다.

MVP에서는 다음과 같이 처리합니다.

```text
자동차 기준 거리/시간 → 자체 휴리스틱 → 대중교통 예상값
```

따라서 최종 결과에 반드시 다음 문구를 포함합니다.

```text
대중교통 시간과 비용은 실시간 환승 경로가 아닌 거리 기반 참고용 추정치입니다.
```

---

## 21. 기대 효과

### 21-1. 사용자 측면

TripRoute를 통해 사용자는 다음 효과를 얻을 수 있습니다.

* 여행 계획 검색 시간을 줄일 수 있음
* 처음 가는 지역에서도 동선을 쉽게 파악할 수 있음
* 개인 취향에 맞는 관광지를 추천받을 수 있음
* 여행 일정의 과밀도를 줄일 수 있음
* 이동수단별 예상 비용을 한 번에 확인할 수 있음

### 21-2. 개발 및 학습 측면

개발 측면에서는 다음 학습 효과를 얻을 수 있습니다.

* LangGraph 기반 Agentic Workflow 구현 경험
* RAG 구조 설계 및 구현 경험
* 공공데이터 API 활용 경험
* 이동정보 API 활용 경험
* LLM 기반 구조화 출력 활용 경험
* FastAPI + Gradio 기반 로컬 데모 구현 경험
* Supabase pgvector 기반 벡터 검색 경험

---

## 22. 팀 정보

---

## 23. Repository

```text
https://github.com/bbbj00/team06-TripRoute
```

---

## 24. License

본 프로젝트는 학습 및 제출용 MVP 데모 프로젝트입니다.

상업적 서비스가 아니며, 외부 API 사용 시 각 API 제공사의 이용약관과 호출 제한을 준수해야 합니다.
