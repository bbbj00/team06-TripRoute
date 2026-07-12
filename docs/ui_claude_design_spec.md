# TripRoute UI 디자인 스펙 (Claude.ai 스타일)

현재 `ui/gradio_app.py`의 Gradio 인터페이스에 Claude.ai 느낌의 톤앤매너를 적용하기 위한 디자인 스펙입니다.

> **면책 문구**: 아래 컬러 HEX 값은 Claude.ai를 실측(devtools 인스펙션)한 값이 아니라, 공개적으로 회자되는 커뮤니티 추정치를 참고한 **근사값**입니다. 포인트 컬러(`#D97757`)도 출처에 따라 `#CC785C`, `#DA7756` 등으로 다르게 언급되는 값 중 하나이며, Anthropic이 공식 배포한 브랜드 컬러가 아닙니다. "Claude.ai와 100% 동일"이 아니라 "Claude.ai 무드보드 참고"로 이해해주세요.

> **검토 이력**: 이 문서는 4개 관점(시각 충실도 / Gradio 기술 구현 가능성 / WCAG 접근성 / TripRoute 프로젝트 적합성)의 에이전트 비평 및 상호 토론을 거쳐 개정되었습니다. 핵심 결론은 **"색상 리스킨보다 정보구조 재설계가 먼저"**입니다 — TripRoute 응답은 Claude.ai식 짧은 대화 텍스트가 아니라 `formatter.py`가 만들어내는 최대 5~6개의 markdown 표(일정표, 이동 동선, 비용표, 디버그용 React trace 등)를 이어붙인 "다중 테이블 리포트"이기 때문입니다. 상세 내용은 문서 하단 [8. 검토 요약](#8-검토-요약-멀티-에이전트-비평)을 참고하세요.

---

## 1. 컬러 팔레트

| 용도 | 라이트 모드 | 설명 |
|---|---|---|
| 배경 (base) | `#F5F4ED` | 따뜻한 아이보리/크림 배경 (추정치) |
| 표면 (카드/사이드박스) | `#FAFAF7` | 배경보다 살짝 밝은 카드 표면 |
| 포인트 컬러 (primary) | `#D97757` | 테라코타 오렌지 (커뮤니티 추정값 중 하나) |
| 포인트 hover | `#C4633F` | 버튼 hover 시 살짝 어둡게 |
| 본문 텍스트 | `#3D3929` | 다크 브라운/차콜 (순수 검정 대신) |
| 보조 텍스트 | `#6B6A62` | 캡션, 힌트 텍스트 — *배경 대비 AA(4.5:1) 확보를 위해 원안 `#87867F`(대비 ≈3.3:1, AA 미달)보다 어둡게 조정* |
| 테두리 | `#D8D5C9` | 카드/입력창 보더 — *원안 `#E5E3DA`는 배경과 거의 구분 안 돼(대비 ≈1.2:1) 살짝 진하게 조정* |
| 사용자 채팅 버블 | `#EDEADF` | 은은한 베이지 |
| AI 응답 영역 | 배경 없음 (base와 동일) | *원안은 흰 카드+테두리였으나, 실제 Claude.ai처럼 카드 없이 페이지 배경 위에 흐르는 형태로 변경 (§4.3 참고)* |

⚠️ **Primary 버튼 대비 이슈**: `#D97757` 배경 + 흰 텍스트는 명도 대비 ≈3.12:1로 WCAG AA(4.5:1) 미달이며, 오히려 hover색(`#C4633F`, ≈4.04:1)이 더 낫다는 역전 현상이 있습니다. 버튼 배경은 **hover색인 `#C4633F`를 기본 상태로 사용**하고, `#D97757`은 더 연한 보조 요소(태그, 아이콘 등)에만 쓰는 것을 권장합니다.

다크 모드: 배경 `#1F1E1D`, 카드 `#2B2A28`, 텍스트 `#E8E6DC`, 포인트 컬러는 라이트와 동일. 단, 반드시 §5의 `@media (prefers-color-scheme: dark)` 블록으로 구현해야 하며 프로즈 서술만으로는 적용되지 않습니다.

---

## 2. 타이포그래피

- **제목(H1~H3)과 본문/UI 모두 sans 계열로 통일**: `"Pretendard", "Inter", -apple-system, sans-serif`, 제목은 `font-weight: 700`으로 위계를 줌
  - *원안은 제목에 serif(Georgia + Noto Serif KR)를 지정했으나, 실제 Claude.ai 제품 UI는 처음부터 끝까지 산세리프이고(serif인 Tiempos는 anthropic.com 마케팅 사이트의 특징), 또한 Georgia는 한글 글리프가 없어 한/영 혼용 시 Noto Serif KR로 강제 폴백되어 굵기·x-height가 어긋나는 문제가 있어 제거함*
- 기본 폰트 크기 15~16px, line-height 1.6 이상
- **Pretendard 실제 로딩 필수**: Pretendard는 Google Fonts 카탈로그에 없어 `gr.themes.GoogleFont("Pretendard")`로 로드되지 않습니다. 아래처럼 CDN을 명시적으로 불러와야 합니다.

```html
<link rel="stylesheet" as="style" crossorigin
  href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
```

Gradio에서는 `gr.Blocks(head=...)`에 위 `<link>` 태그를 주입하면 됩니다. 로딩에 실패하면 `Inter` → 시스템 한글 폰트(맑은 고딕 등) 순으로 조용히 폴백됩니다.

---

## 3. 레이아웃 & 여백

- 전체 컨테이너 `max-width: 1050px`, 중앙 정렬 (기존 유지)
- 카드/사이드박스 라운드: `border-radius: 16px`
- 카드 내부 패딩 `20px` 이상
- 그림자: `box-shadow: 0 1px 2px rgba(0,0,0,0.06)` (원안 0.04는 §1 테두리 대비 문제와 겹쳐 시인성이 낮았음)

---

## 4. 컴포넌트별 적용

> ⚠️ **구조적 선행 작업**: 아래 4.1~4.5는 색/타이포 스타일링이며, 실제 적용은 반드시 [§6 정보구조 재설계](#6-정보구조-재설계-최우선)를 먼저 끝낸 뒤 진행해야 재작업을 피할 수 있습니다.

### 4.1 타이틀 영역 (`#title-box`)
- 배경 없이 투명, sans-bold 텍스트로 강조
- H1은 `#3D3929`, 부제(설명 문구)는 `#6B6A62`

### 4.2 사이드 설정 박스 (`.option-box`)
- 배경 `#FAFAF7`, 보더 `1px solid #D8D5C9`, `border-radius: 16px`
- 라디오 버튼/슬라이더 선택 색상 → 포인트 컬러(`#C4633F`)로 오버라이드 (비텍스트 대비 3:1 확보 위해 `#D97757` 대신 hover색 사용)

### 4.3 일반 대화 텍스트 vs 여행 계획 결과 — 분리 렌더링
- **일반 대화 텍스트**(짧은 질문/응답): Claude.ai처럼 카드 없이 페이지 배경 위에 마크다운으로 흐르듯 표시. 사용자 메시지만 `#EDEADF` 베이지 버블(우측 정렬, 라운드 18px)로 감싸고, AI 텍스트는 배경/테두리 없이 좌측 정렬로 표시.
- **여행 계획 결과**(다중 markdown 표): 챗봇 버블에 그대로 넣지 않고 [§6](#6-정보구조-재설계-최우선)에서 정의하는 별도 결과 패널/카드로 렌더링. 발화자 구분을 색에만 의존하지 않도록 "나 / TripRoute AI" 같은 텍스트 레이블을 함께 표시.
- 표(table) 자체 스타일: 헤더 배경 `#FAFAF7`, 셀 패딩 `8px 12px`, 바깥 라운드 `12px`, 보더 `1px solid #D8D5C9` — 표 6개가 연속돼도 "따뜻한 톤"과 "구조적 가독성"이 공존하도록 함

### 4.4 버튼
- Primary(`#send-button`, "여행 계획 생성"): 배경 `#C4633F`(AA 대비 확보), 텍스트 화이트, hover 시 `#B0532F`
- Secondary("대화 초기화"): 배경 투명, 보더 `1px solid #D8D5C9`, 텍스트 `#3D3929`

### 4.5 입력창 (Textbox)
- 배경 `#FFFFFF`, 보더 `1px solid #D8D5C9`, 포커스 시 보더 `#C4633F`, 라운드 `12px`
- **`value=DEFAULT_MESSAGE` 대신 `placeholder=DEFAULT_MESSAGE`로 변경**: 현재 코드는 예시 문장을 입력창에 미리 채워두는데(`ui/gradio_app.py`), 사용자가 아무것도 입력하지 않고 Enter/버튼을 누르면 직접 쓰지 않은 문장이 자기 발화처럼 그대로 전송된다. placeholder로 바꿔 빈 입력창 + 안내 문구 형태로 수정.

### 4.6 디버그 정보 (React trace) 숨김
- `create_trip_response`의 `format_trip_plan_markdown(plan=result, include_trace=True)` 호출을 검토 — 실행 흐름(Step/Action/Description/Parser) 표는 개발자용 정보이므로 기본은 숨기고, `gr.Accordion("실행 과정 보기", open=False)`로 접어서 필요할 때만 펼치는 형태 권장.

### 4.7 로딩/진행 상태
- 멀티 에이전트 체인(Coordinator → Route Planner → Financial) 실행은 수 초가 걸릴 수 있음. 현재는 완성된 결과를 한 번에 반환하는 구조라 대기 중 화면이 멈춘 것처럼 보일 수 있음.
- `gr.Progress()` 또는 상태 메시지("여행 계획을 짜는 중...")를 최소한 추가해 "먹통처럼 보이는" 인상을 방지.

---

## 5. CSS 초안 (`ui/gradio_app.py`의 `CUSTOM_CSS` 대체용)

```css
:root {
    --tr-bg: #F5F4ED;
    --tr-surface: #FAFAF7;
    --tr-primary: #C4633F;
    --tr-primary-hover: #B0532F;
    --tr-text: #3D3929;
    --tr-text-muted: #6B6A62;
    --tr-border: #D8D5C9;
    --tr-bubble-user: #EDEADF;
}

.gradio-container {
    max-width: 1050px !important;
    margin: 0 auto !important;
    background: var(--tr-bg) !important;
    font-family: "Pretendard", "Inter", -apple-system, sans-serif;
}

#title-box h1 {
    color: var(--tr-text);
    font-weight: 700;
    margin-bottom: 4px;
}

#title-box p {
    color: var(--tr-text-muted);
}

.option-box {
    background: var(--tr-surface);
    border: 1px solid var(--tr-border);
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
}

/* 라디오/슬라이더 포인트 컬러 오버라이드 */
.option-box input[type="radio"]:checked,
.option-box .wrap.svelte-1p9xokt input:checked {
    accent-color: var(--tr-primary);
}
.option-box input[type="range"] {
    accent-color: var(--tr-primary);
}

#chatbot {
    min-height: 520px;
    background: var(--tr-bg);
    border-radius: 16px;
}

/* 사용자 버블만 배경 지정 (AI 응답은 무카드) */
#chatbot .bubble.user-row .bubble {
    background: var(--tr-bubble-user) !important;
    border-radius: 18px !important;
}
#chatbot .bubble.bot-row .bubble,
#chatbot .panel.bot-row {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}

/* markdown 표 스타일 */
#chatbot table {
    border-collapse: collapse;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--tr-border);
}
#chatbot th {
    background: var(--tr-surface);
    padding: 8px 12px;
}
#chatbot td {
    padding: 8px 12px;
    border-top: 1px solid var(--tr-border);
}

#message-input textarea:focus {
    border-color: var(--tr-primary) !important;
}

#send-button {
    min-height: 44px;
    font-weight: 700;
    background: var(--tr-primary) !important;
    color: #fff !important;
    border-radius: 12px;
}

#send-button:hover {
    background: var(--tr-primary-hover) !important;
}

@media (prefers-color-scheme: dark) {
    :root {
        --tr-bg: #1F1E1D;
        --tr-surface: #2B2A28;
        --tr-text: #E8E6DC;
        --tr-text-muted: #B5B3A8;
        --tr-border: #3A3835;
        --tr-bubble-user: #3A362E;
    }
}
```

⚠️ `#chatbot .bubble.bot-row`, `.panel.bot-row` 같은 셀렉터는 Gradio가 공식 문서화한 안정 API가 아니라 Svelte 컴파일 시 부여되는 내부 구현 클래스입니다. `pyproject.toml`의 `gradio>=6.20.0`처럼 상한이 없는 버전 고정 상태에서는 마이너 업데이트로 클래스명이 바뀌어 이 CSS가 조용히 깨질 수 있으니, Gradio 버전을 올릴 때마다 실제 렌더링을 확인하세요.

---

## 6. 정보구조 재설계 (최우선)

여행 계획 결과(최대 6개의 markdown 표: 조건 요약/시간대별 일정/이동 동선/비용표/주의사항/React trace)를 좁은 챗봇 버블(폭 75%)에 그대로 넣으면 표가 심하게 좁아지거나 줄바꿈이 깨지고, 세로 스크롤이 이중으로 겹치는 문제가 있습니다.

**권장 구조**: 일반 대화는 Claude.ai식 무카드 텍스트 스트림으로 유지하고, 여행 계획 생성 결과만 채팅 스트림에서 분리해 전용 결과 패널(오른쪽 별도 컬럼 또는 결과 전용 탭)로 렌더링하는 하이브리드 구조를 채택합니다. 이 작업을 §4~§5의 색상/타이포 작업보다 먼저 진행해야, 나중에 레이아웃을 바꿀 때 버블 전용 CSS를 다시 손보는 재작업을 피할 수 있습니다.

---

## 7. 적용 우선순위

1. **정보구조 재설계** — 여행 계획 결과를 버블에서 분리해 별도 패널/탭으로 (§6)
2. **React trace 기본 숨김 + 입력창 placeholder 전환** — 코드 변경 2줄 수준, 리스크 낮음 (§4.5, §4.6)
3. **CSS 색상/타이포 교체** — §5 초안 적용 (버튼 대비, 보조텍스트 대비, 폰트 로딩 포함)
4. **표 스타일 + 버블 색 구분 세부 조정** — Gradio 내부 셀렉터 의존 부분이라 버전 업그레이드 시 재검증 필요 (§4.3, §5)
5. **로딩 상태 / 다크 모드** — 여유 있을 때 추가 (§4.7, §5)

---

## 8. 검토 요약 (멀티 에이전트 비평)

이 문서는 4개 관점(①시각 충실도 ②Gradio 기술 구현 가능성 ③WCAG 접근성 ④TripRoute 프로젝트 적합성)의 독립 비평과, 각 관점이 서로의 지적사항에 대해 동의/반박한 토론을 거쳐 개정되었습니다.

**4개 관점 모두 동의한 핵심 결론**: 원안은 색상 HEX·폰트·둥근 모서리 같은 "표면 리스킨"에만 집중했지만, TripRoute의 실제 응답은 Claude.ai식 짧은 대화가 아니라 다중 테이블 리포트이므로, 이 콘텐츠 구조를 그대로 챗봇 버블에 욱여넣는 것 자체가 근본 문제라는 데 수렴했습니다.

**주요 반영 사항**:
- 근거 없이 "실측값"처럼 제시됐던 HEX 팔레트에 면책 문구 추가
- Primary 버튼(`#D97757`+흰 텍스트, 대비 ≈3.12:1)과 보조 텍스트(`#87867F`, 대비 ≈3.3~3.5:1)의 WCAG AA 미달을 색상 조정으로 해결
- 제목 serif(Georgia+Noto Serif KR) 조합이 한/영 혼용 시 통일성이 깨지는 문제 → sans-bold로 통일
- Pretendard 웹폰트가 실제로는 로드되지 않던 문제 → CDN 링크 명시
- AI 응답에 대칭적 카드/테두리를 부여한 것이 실제 Claude.ai의 비대칭 구조와 다르다는 지적 → 일반 대화는 무카드로 변경
- 우선순위가 색상 교체부터 시작했던 문제 → 정보구조 재설계를 최우선으로 재배치
- 입력창 `value` 사전 채움, React trace 기본 노출, 로딩 상태 부재 등 상호작용/콘텐츠 이슈 추가 반영

**의견이 갈렸던 지점**: "AI 버블에서 카드를 완전히 제거(충실도 우선)" vs "표 콘텐츠는 경계를 뚜렷이(가독성 우선)" — 두 요구를 모두 만족하도록 §4.3처럼 콘텐츠 유형별 하이브리드 렌더링으로 절충했습니다.
