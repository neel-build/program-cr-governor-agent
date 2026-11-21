import pandas as pd

REQUIRED_COLUMNS = [
    "task_id",
    "task_name",
    "phase",
    "predecessors",
    "duration_days",
    "effort_hours",
    "daily_rate_usd",
]


def validate_project_plan(df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Validate required columns, numeric fields, and unique task IDs."""
    errors = []

    if df.empty:
        return False, ["The uploaded CSV file is empty."]

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        return False, [f"Missing required columns: {', '.join(missing_cols)}"]

    if df["task_id"].isna().any() or (df["task_id"].astype(str).str.strip() == "").any():
        errors.append("One or more rows have a blank task_id.")

    if df["task_id"].duplicated().any():
        dupes = df[df["task_id"].duplicated()]["task_id"].tolist()
        errors.append(f"Duplicate task_id values found: {', '.join(map(str, dupes))}")

    for num_col in ["duration_days", "effort_hours", "daily_rate_usd"]:
        converted = pd.to_numeric(df[num_col], errors="coerce")
        if converted.isna().any():
            errors.append(f"Column '{num_col}' contains non-numeric or missing values.")
        elif (converted < 0).any():
            errors.append(f"Column '{num_col}' cannot contain negative numbers.")

    return len(errors) == 0, errors


def compute_baseline_metrics(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Compute deterministic baseline cost and effort metrics."""
    plan = df.copy()
    plan["predecessors"] = plan["predecessors"].fillna("").astype(str).str.strip()
    plan["duration_days"] = pd.to_numeric(plan["duration_days"])
    plan["effort_hours"] = pd.to_numeric(plan["effort_hours"])
    plan["daily_rate_usd"] = pd.to_numeric(plan["daily_rate_usd"])

    # Deterministic task cost = duration in days * daily rate
    plan["baseline_cost_usd"] = plan["duration_days"] * plan["daily_rate_usd"]

    summary = {
        "total_tasks": int(len(plan)),
        "total_effort_hours": float(plan["effort_hours"].sum()),
        "total_task_days": float(plan["duration_days"].sum()),
        "total_baseline_cost_usd": float(plan["baseline_cost_usd"].sum()),
    }

    return plan, summary
