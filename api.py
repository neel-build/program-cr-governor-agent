from typing import Optional
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.baseline_engine import validate_project_plan
from src.simulation_engine import simulate_change_request

app = FastAPI(
    title="Program CR Governor API",
    description="Deterministic schedule, effort, and budget impact engine for enterprise SaaS Change Requests.",
    version="1.0.0",
)

SAMPLE_CSV = "data/sample_project_plan.csv"


def _load_plan() -> pd.DataFrame:
    df = pd.read_csv(SAMPLE_CSV)
    return df


class SimulationRequest(BaseModel):
    task_id: str
    duration_delta_days: float = 0.0
    effort_delta_hours: float = 0.0
    daily_rate_override: Optional[float] = None
    scenario_name: Optional[str] = None


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Program CR Governor API"}


@app.get("/baseline")
def get_baseline():
    df = _load_plan()
    res = simulate_change_request(
        base_df=df,
        task_adjustments={},
        new_tasks=[],
        scenario_name="Approved Program Baseline",
    )
    sim = res["simulated"]
    return {
        "project_duration_days": sim["project_duration_days"],
        "total_baseline_cost_usd": sim["total_baseline_cost_usd"],
        "total_effort_hours": sim["total_effort_hours"],
        "tasks": sim["schedule_df"].to_dict(orient="records"),
    }


@app.post("/simulate")
def run_simulation(req: SimulationRequest):
    df = _load_plan()
    valid_ids = df["task_id"].astype(str).tolist()
    if req.task_id not in valid_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown task_id '{req.task_id}'. Valid task IDs: {', '.join(valid_ids)}",
        )

    scenario = req.scenario_name or f"CR Simulation ({req.task_id}: {req.duration_delta_days:+.1f}d, {req.effort_delta_hours:+.0f}h)"
    res = simulate_change_request(
        base_df=df,
        task_adjustments={
            req.task_id: {
                "duration_delta_days": req.duration_delta_days,
                "effort_delta_hours": req.effort_delta_hours,
                "daily_rate_override": req.daily_rate_override,
                "extra_predecessors": [],
            }
        },
        new_tasks=[],
        scenario_name=scenario,
    )
    sim = res["simulated"]
    deltas = res["deltas"]
    return {
        "scenario_name": res["scenario_name"],
        "projected_duration_days": sim["project_duration_days"],
        "duration_delta_days": deltas["project_duration_delta_days"],
        "projected_budget_usd": sim["total_baseline_cost_usd"],
        "budget_delta_usd": deltas["total_cost_delta_usd"],
        "projected_effort_hours": sim["total_effort_hours"],
        "schedule": sim["schedule_df"].to_dict(orient="records"),
    }
