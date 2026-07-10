from fastapi import FastAPI

from app.agents.react_loop import run_triproute_react_loop
from app.schemas.request import TripPlanRequest
from app.schemas.response import TripPlanResponse


app = FastAPI(
    title="TripRoute API",
    description="Agentic Workflow 기반 여행 일정 자동 생성 API",
    version="0.1.0",
)


@app.get("/")
def health_check() -> dict:
    return {
        "status": "ok",
        "message": "TripRoute API is running",
    }


@app.post("/trip/plan", response_model=TripPlanResponse)
def create_trip_plan(request: TripPlanRequest) -> TripPlanResponse:
    result = run_triproute_react_loop(
        user_input=request.user_input,
        transport_mode=request.transport_mode,
        people_count=request.people_count,
    )

    return TripPlanResponse(
    condition_summary=result["condition_summary"],
    daily_schedule=result["daily_schedule"],
    route_summary=result["route_summary"],
    cost_summary=result["cost_summary"],
    warnings=result["warnings"],
    react_trace=result["react_trace"],
)