import pandas as pd
from src.baseline_engine import compute_baseline_metrics
from src.schedule_engine import compute_critical_path_schedule


def simulate_change_request(
    base_df: pd.DataFrame,
    task_adjustments: dict[str, dict] | None = None,
    new_tasks: list[dict] | None = None,
    scenario_name: str = "Simulated CR Scenario",
) -> dict:
    """
    Deterministically apply change request adjustments to a project plan and
    compare baseline vs. simulated schedule, effort, and cost.

    task_adjustments format:
      {
        "T05": {
          "duration_delta_days": 5.0,
          "effort_delta_hours": 40.0,
          "daily_rate_override": None,
          "extra_predecessors": [],
        }
      }
    """
    base_plan, base_cost_summary = compute_baseline_metrics(base_df)
    base_sched, base_sched_summary = compute_critical_path_schedule(base_plan)

    sim_df = base_plan.copy()
    sim_df["task_id"] = sim_df["task_id"].astype(str).str.strip()
    sim_df["predecessors"] = sim_df["predecessors"].fillna("").astype(str).str.strip()

    adjustments = task_adjustments or {}
    applied_changes = []

    for tid, adj in adjustments.items():
        clean_tid = str(tid).strip()
        mask = sim_df["task_id"] == clean_tid
        if not mask.any():
            raise ValueError(f"Change request references unknown task_id '{clean_tid}'.")

        dur_delta = float(adj.get("duration_delta_days", 0.0) or 0.0)
        eff_delta = float(adj.get("effort_delta_hours", 0.0) or 0.0)
        rate_override = adj.get("daily_rate_override", None)
        extra_preds = adj.get("extra_predecessors", []) or []

        new_dur = float(sim_df.loc[mask, "duration_days"].iloc[0]) + dur_delta
        if new_dur < 0:
            raise ValueError(f"Task '{clean_tid}' duration cannot drop below 0 days.")

        new_eff = float(sim_df.loc[mask, "effort_hours"].iloc[0]) + eff_delta
        if new_eff < 0:
            raise ValueError(f"Task '{clean_tid}' effort hours cannot drop below 0.")

        sim_df.loc[mask, "duration_days"] = new_dur
        sim_df.loc[mask, "effort_hours"] = new_eff

        if rate_override is not None:
            new_rate = float(rate_override)
            if new_rate < 0:
                raise ValueError(f"Task '{clean_tid}' daily rate cannot be negative.")
            sim_df.loc[mask, "daily_rate_usd"] = new_rate

        if extra_preds:
            existing_raw = str(sim_df.loc[mask, "predecessors"].iloc[0]).strip()
            existing_list = [p.strip() for p in existing_raw.split(";") if p.strip()]
            for ep in extra_preds:
                ep_clean = str(ep).strip()
                if ep_clean and ep_clean not in existing_list:
                    existing_list.append(ep_clean)
            sim_df.loc[mask, "predecessors"] = ";".join(existing_list)

        applied_changes.append(
            {
                "task_id": clean_tid,
                "duration_delta_days": dur_delta,
                "effort_delta_hours": eff_delta,
                "daily_rate_override": rate_override,
                "extra_predecessors": extra_preds,
            }
        )

    for nt in new_tasks or []:
        nt_id = str(nt["task_id"]).strip()
        if (sim_df["task_id"] == nt_id).any():
            raise ValueError(f"New task_id '{nt_id}' already exists in project plan.")
        preds_val = nt.get("predecessors", "")
        if isinstance(preds_val, list):
            preds_str = ";".join([str(p).strip() for p in preds_val if str(p).strip()])
        else:
            preds_str = str(preds_val or "").strip()

        new_row = {
            "task_id": nt_id,
            "task_name": str(nt.get("task_name", f"CR Task {nt_id}")).strip(),
            "phase": str(nt.get("phase", "Build")).strip(),
            "predecessors": preds_str,
            "duration_days": float(nt.get("duration_days", 0.0)),
            "effort_hours": float(nt.get("effort_hours", 0.0)),
            "daily_rate_usd": float(nt.get("daily_rate_usd", 0.0)),
        }
        sim_df = pd.concat([sim_df, pd.DataFrame([new_row])], ignore_index=True)
        applied_changes.append({"added_task": new_row})

    sim_plan, sim_cost_summary = compute_baseline_metrics(sim_df)
    sim_sched, sim_sched_summary = compute_critical_path_schedule(sim_plan)

    duration_delta_days = round(
        sim_sched_summary["project_duration_days"] - base_sched_summary["project_duration_days"],
        2,
    )
    cost_delta_usd = round(
        sim_cost_summary["total_baseline_cost_usd"] - base_cost_summary["total_baseline_cost_usd"],
        2,
    )
    effort_delta_hours = round(
        sim_cost_summary["total_effort_hours"] - base_cost_summary["total_effort_hours"],
        2,
    )

    return {
        "scenario_name": scenario_name,
        "applied_changes": applied_changes,
        "baseline": {
            **base_cost_summary,
            **base_sched_summary,
            "schedule_df": base_sched,
        },
        "simulated": {
            **sim_cost_summary,
            **sim_sched_summary,
            "schedule_df": sim_sched,
        },
        "deltas": {
            "project_duration_delta_days": duration_delta_days,
            "total_cost_delta_usd": cost_delta_usd,
            "total_effort_delta_hours": effort_delta_hours,
        },
    }
