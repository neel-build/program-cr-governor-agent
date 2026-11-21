import pandas as pd
from src.baseline_engine import compute_baseline_metrics, validate_project_plan


def test_sample_plan_validates_and_computes_exact_baseline():
    df = pd.read_csv("data/sample_project_plan.csv")
    is_valid, errors = validate_project_plan(df)
    assert is_valid is True
    assert errors == []

    plan_df, summary = compute_baseline_metrics(df)
    assert summary["total_tasks"] == 12
    assert summary["total_effort_hours"] == 516.0
    assert summary["total_task_days"] == 64.0
    assert summary["total_baseline_cost_usd"] == 47350.0
    assert "baseline_cost_usd" in plan_df.columns


def test_validation_catches_missing_columns():
    bad_df = pd.DataFrame({"task_id": ["T01"], "task_name": ["Kickoff"]})
    is_valid, errors = validate_project_plan(bad_df)
    assert is_valid is False
    assert "Missing required columns" in errors[0]


def test_validation_catches_duplicate_task_ids():
    df = pd.read_csv("data/sample_project_plan.csv")
    df.loc[1, "task_id"] = "T01"
    is_valid, errors = validate_project_plan(df)
    assert is_valid is False
    assert any("Duplicate task_id" in err for err in errors)
