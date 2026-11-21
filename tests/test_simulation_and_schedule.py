import pandas as pd
import pytest
from src.cr_interpreter import interpret_change_request
from src.schedule_engine import compute_critical_path_schedule
from src.simulation_engine import simulate_change_request


def test_critical_path_calculation():
    df = pd.read_csv("data/sample_project_plan.csv")
    sched_df, summary = compute_critical_path_schedule(df)
    assert summary["project_duration_days"] == 40.0
    assert summary["critical_path_tasks"] == ["T01", "T03", "T05", "T07", "T09", "T10", "T11", "T12"]
    assert "total_float_days" in sched_df.columns


def test_circular_dependency_raises_error():
    df = pd.DataFrame(
        [
            {"task_id": "T01", "task_name": "A", "phase": "Design", "predecessors": "T02", "duration_days": 3, "effort_hours": 24, "daily_rate_usd": 600},
            {"task_id": "T02", "task_name": "B", "phase": "Build", "predecessors": "T01", "duration_days": 4, "effort_hours": 32, "daily_rate_usd": 700},
        ]
    )
    with pytest.raises(ValueError, match="Circular dependency"):
        compute_critical_path_schedule(df)


def test_simulate_change_request_deltas():
    df = pd.read_csv("data/sample_project_plan.csv")
    res = simulate_change_request(
        base_df=df,
        task_adjustments={"T05": {"duration_delta_days": 5, "effort_delta_hours": 40}},
    )
    assert res["baseline"]["project_duration_days"] == 40.0
    assert res["simulated"]["project_duration_days"] == 45.0
    assert res["deltas"]["project_duration_delta_days"] == 5.0
    assert res["deltas"]["total_cost_delta_usd"] == 4250.0
    assert res["deltas"]["total_effort_delta_hours"] == 40.0


def test_cr_interpreter_fallback_mode():
    valid_ids = ["T01", "T02", "T03", "T04", "T05"]
    parsed = interpret_change_request(
        cr_text="Add 4 days and 32 hours to T05 for webhook support",
        valid_task_ids=valid_ids,
        api_key="",
    )
    assert parsed["source"] == "deterministic_fallback"
    assert parsed["task_adjustments"]["T05"]["duration_delta_days"] == 4.0
    assert parsed["task_adjustments"]["T05"]["effort_delta_hours"] == 32.0
