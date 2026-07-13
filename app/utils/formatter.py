# app/utils/formatter.py

from typing import Any, Dict, Iterable, List


def _text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else default
    text = str(value).strip()
    return text if text else default


def _money(value: Any) -> str:
    try:
        return f"{int(value):,}원"
    except (TypeError, ValueError):
        return "-"


def _escape_md(value: Any) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: List[str], rows: Iterable[Iterable[Any]]) -> str:
    header_line = "| " + " | ".join(headers) + " |"
    divider_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    body_lines = []
    for row in rows:
        body_lines.append(
            "| " + " | ".join(_escape_md(cell) for cell in row) + " |"
        )

    if not body_lines:
        body_lines.append(
            "| " + " | ".join(["-"] * len(headers)) + " |"
        )

    return "\n".join([header_line, divider_line, *body_lines])


def format_condition_summary(plan: Dict[str, Any]) -> str:
    condition = plan.get("condition_summary", {})

    rows = [
        ["도시", condition.get("city")],
        ["계절", condition.get("season")],
        ["기간", condition.get("duration")],
        ["여행 취향", condition.get("travel_style", [])],
        ["일정 강도", condition.get("schedule_intensity")],
        ["이동수단", condition.get("transport_mode")],
        ["인원수", f"{condition.get('people_count', '-')}명"],
        ["입력 파서", condition.get("parser")],
    ]

    return "## 여행 조건 요약\n\n" + _markdown_table(["항목", "내용"], rows)


def format_daily_schedule(plan: Dict[str, Any]) -> str:
    """
    일정을 Day별로 묶어서 "### Day N" 소제목 + 표를 반복 출력한다.
    (Day 컬럼을 표에서 빼고 소제목으로 대체 — 표마다 같은 값이 반복되던 문제 해결)
    """
    schedule = plan.get("daily_schedule", [])

    if not schedule:
        return "## 시간대별 일정표\n\n" + _markdown_table(
            ["시간대", "장소", "추천 이유", "동선 메모"], []
        )

    days: Dict[Any, List[Dict[str, Any]]] = {}
    order: List[Any] = []
    for item in schedule:
        day = item.get("day")
        if day not in days:
            days[day] = []
            order.append(day)
        days[day].append(item)

    sections = ["## 시간대별 일정표"]

    for day in order:
        rows = []
        for item in days[day]:
            rows.append(
                [
                    item.get("time_slot"),
                    item.get("place_name") or item.get("place"),
                    item.get("reason"),
                    item.get("route_memo"),
                ]
            )

        day_label = f"Day {day}" if day is not None else "Day -"
        sections.append(f"### {day_label}")
        sections.append(
            _markdown_table(["시간대", "장소", "추천 이유", "동선 메모"], rows)
        )

    return "\n\n".join(sections)


def format_route_summary(plan: Dict[str, Any]) -> str:
    routes = plan.get("route_summary", [])

    rows = []
    for route in routes:
        rows.append(
            [
                route.get("from"),
                route.get("to"),
                route.get("distance_km"),
                route.get("estimated_time")
                or route.get("estimated_time_minutes"),
                route.get("transport_mode"),
                route.get("memo"),
            ]
        )

    return "## 이동 동선 요약\n\n" + _markdown_table(
        ["출발", "도착", "거리(km)", "예상 시간", "이동수단", "메모"],
        rows,
    )


def format_cost_summary(plan: Dict[str, Any]) -> str:
    cost = plan.get("cost_summary", {})

    total = cost.get("total_cost", cost.get("total", 0))

    rows = [
        ["교통비", _money(cost.get("transport_cost"))],
        ["식비", _money(cost.get("food_cost"))],
        ["카페비", _money(cost.get("cafe_cost"))],
        ["입장료", _money(cost.get("admission_cost"))],
        ["숙박비", _money(cost.get("lodging_cost"))],
        ["총액", _money(total)],
    ]

    return "## 예상 비용표\n\n" + _markdown_table(["항목", "예상 비용"], rows)


def format_warnings(plan: Dict[str, Any]) -> str:
    warnings = plan.get("warnings", [])

    if not warnings:
        return "## 주의사항\n\n- 별도 주의사항이 없습니다."

    lines = ["## 주의사항"]
    for warning in warnings:
        lines.append(f"- {_text(warning)}")

    return "\n".join(lines)


def format_react_trace(plan: Dict[str, Any]) -> str:
    trace = plan.get("react_trace", [])

    rows = []
    for item in trace:
        rows.append(
            [
                item.get("step"),
                item.get("action"),
                item.get("description"),
                item.get("parser", "-"),
            ]
        )

    return "## Agentic Workflow 실행 흐름\n\n" + _markdown_table(
        ["Step", "Action", "Description", "Parser"],
        rows,
    )


def format_trip_plan_markdown(
    plan: Dict[str, Any],
    include_trace: bool = True,
) -> str:
    """
    TripRoute 최종 응답 JSON을 Gradio에서 렌더링하기 좋은 Markdown 형식으로 변환한다.
    """

    sections = [
        "# TripRoute 여행 일정 결과",
        format_condition_summary(plan),
        format_daily_schedule(plan),
        format_route_summary(plan),
        format_cost_summary(plan),
        format_warnings(plan),
    ]

    if include_trace:
        sections.append(format_react_trace(plan))

    return "\n\n".join(sections)