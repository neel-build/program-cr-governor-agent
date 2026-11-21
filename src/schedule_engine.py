import networkx as nx
import pandas as pd


def build_dependency_graph(df: pd.DataFrame) -> tuple[nx.DiGraph, list[str]]:
    """Build a directed dependency graph and check for missing predecessors or cycles."""
    errors = []
    graph = nx.DiGraph()

    valid_ids = set(df["task_id"].astype(str).str.strip())

    for _, row in df.iterrows():
        tid = str(row["task_id"]).strip()
        graph.add_node(
            tid,
            task_name=str(row["task_name"]),
            phase=str(row["phase"]),
            duration_days=float(row["duration_days"]),
            effort_hours=float(row["effort_hours"]),
            daily_rate_usd=float(row["daily_rate_usd"]),
        )

    for _, row in df.iterrows():
        tid = str(row["task_id"]).strip()
        raw_preds = "" if pd.isna(row["predecessors"]) else str(row["predecessors"]).strip()
        if not raw_preds:
            continue

        preds = [p.strip() for p in raw_preds.split(";") if p.strip()]
        for pred in preds:
            if pred == tid:
                errors.append(f"Task '{tid}' cannot depend on itself.")
            elif pred not in valid_ids:
                errors.append(f"Task '{tid}' references unknown predecessor '{pred}'.")
            else:
                graph.add_edge(pred, tid)

    if not errors and not nx.is_directed_acyclic_graph(graph):
        errors.append("Circular dependency detected in project plan (cycle found).")

    return graph, errors


def compute_critical_path_schedule(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Compute forward/backward pass CPM schedule metrics and critical path."""
    graph, errors = build_dependency_graph(df)
    if errors:
        raise ValueError("; ".join(errors))

    topo_order = list(nx.topological_sort(graph))

    # Forward pass: Early Start (ES) and Early Finish (EF)
    early_start = {}
    early_finish = {}
    for node in topo_order:
        preds = list(graph.predecessors(node))
        es = max((early_finish[p] for p in preds), default=0.0)
        ef = es + graph.nodes[node]["duration_days"]
        early_start[node] = es
        early_finish[node] = ef

    project_duration_days = max(early_finish.values(), default=0.0)

    # Backward pass: Late Finish (LF) and Late Start (LS)
    late_finish = {}
    late_start = {}
    for node in reversed(topo_order):
        succs = list(graph.successors(node))
        lf = min((late_start[s] for s in succs), default=project_duration_days)
        ls = lf - graph.nodes[node]["duration_days"]
        late_finish[node] = lf
        late_start[node] = ls

    schedule_df = df.copy()
    schedule_df["task_id"] = schedule_df["task_id"].astype(str).str.strip()
    schedule_df["early_start"] = schedule_df["task_id"].map(early_start)
    schedule_df["early_finish"] = schedule_df["task_id"].map(early_finish)
    schedule_df["late_start"] = schedule_df["task_id"].map(late_start)
    schedule_df["late_finish"] = schedule_df["task_id"].map(late_finish)
    schedule_df["total_float_days"] = (
        schedule_df["late_start"] - schedule_df["early_start"]
    ).round(2)
    schedule_df["is_critical"] = schedule_df["total_float_days"] == 0.0

    critical_tasks = schedule_df[schedule_df["is_critical"]]["task_id"].tolist()

    schedule_summary = {
        "project_duration_days": float(project_duration_days),
        "critical_path_tasks": critical_tasks,
        "critical_task_count": int(len(critical_tasks)),
    }

    return schedule_df, schedule_summary
