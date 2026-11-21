import os
import pandas as pd
import streamlit as st
from src.baseline_engine import compute_baseline_metrics, validate_project_plan
from src.cr_interpreter import interpret_change_request
from src.schedule_engine import compute_critical_path_schedule
from src.simulation_engine import simulate_change_request

st.set_page_config(
    page_title="Program CR Governor Copilot",
    layout="wide",
)

st.title("Program CR Governor Copilot")
st.caption("Schedule, Effort & Budget Impact Analysis for Enterprise SaaS Delivery")

st.sidebar.header("1. Program Baseline")
data_source = st.sidebar.radio(
    "Choose project data source:",
    options=["Use Sample Enterprise SaaS Plan", "Upload Project CSV"],
)

df = None
if data_source == "Use Sample Enterprise SaaS Plan":
    df = pd.read_csv("data/sample_project_plan.csv")
else:
    uploaded_file = st.sidebar.file_uploader("Upload project plan (.csv)", type=["csv"])
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)

st.sidebar.header("2. AI Engine Configuration (Optional)")
api_key_input = st.sidebar.text_input(
    "GEMINI_API_KEY (optional — uses fallback if blank)",
    value="",
    type="password",
)

if df is None:
    st.info("Upload a project plan CSV in the sidebar or select the sample SaaS plan to begin.")
    st.stop()

is_valid, errors = validate_project_plan(df)
if not is_valid:
    st.error("Project plan validation failed:")
    for err in errors:
        st.write(f"- {err}")
    st.stop()

plan_df, base_cost_summary = compute_baseline_metrics(df)
try:
    base_sched_df, base_sched_summary = compute_critical_path_schedule(plan_df)
except ValueError as exc:
    st.error(f"Dependency graph error: {exc}")
    st.stop()

st.subheader("Approved Program Baseline")
b1, b2, b3, b4, b5 = st.columns(5)
b1.metric("Workstream Tasks", base_cost_summary["total_tasks"])
b2.metric("Critical Path Duration", f"{base_sched_summary['project_duration_days']:.0f} days")
b3.metric("Total Effort (Hrs)", f"{base_cost_summary['total_effort_hours']:,.0f} hrs")
b4.metric("Cumulative Task Days", f"{base_cost_summary['total_task_days']:,.0f} days")
b5.metric("Baseline Budget", f"${base_cost_summary['total_baseline_cost_usd']:,.2f}")
st.write("**Baseline Critical Path:**", " -> ".join(base_sched_summary["critical_path_tasks"]))

with st.expander("View Baseline Task & Schedule Table", expanded=False):
    st.dataframe(base_sched_df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("3. Change Request Intake & PM Validation")

default_cr = "Add 4 days and 32 effort hours to T05 for multi-currency ERP webhook support."
cr_text = st.text_area("Change Request (CR) Description:", value=default_cr, height=90)

valid_task_ids = plan_df["task_id"].astype(str).tolist()

if st.button("Analyze Change Request", type="secondary"):
    try:
        parsed = interpret_change_request(
            cr_text=cr_text,
            valid_task_ids=valid_task_ids,
            api_key=api_key_input.strip() or None,
        )
        st.session_state["parsed_cr"] = parsed
        st.session_state.pop("sim_result", None)
    except Exception as exc:
        st.error(f"Failed to interpret change request: {exc}")


if "parsed_cr" not in st.session_state:
    st.session_state["parsed_cr"] = interpret_change_request(
        cr_text=default_cr,
        valid_task_ids=valid_task_ids,
        api_key=api_key_input.strip() or None,
    )

parsed_cr = st.session_state["parsed_cr"]
st.caption(f"Analysis Engine: `{parsed_cr.get('source', 'unknown')}` — {parsed_cr.get('rationale', '')}")

parsed_tasks = list(parsed_cr.get("task_adjustments", {}).keys())
default_task = parsed_tasks[0] if parsed_tasks and parsed_tasks[0] in valid_task_ids else ("T05" if "T05" in valid_task_ids else valid_task_ids[0])
parse_sig = f"{default_task}_{len(parsed_tasks)}_{parsed_cr.get('rationale', '')[:20]}"

target_task = st.selectbox(
    "Impacted Task / Milestone:",
    options=valid_task_ids,
    index=valid_task_ids.index(default_task),
    key=f"task_select_{parse_sig}",
)
existing_adj = parsed_cr.get("task_adjustments", {}).get(target_task, {})

c_dur, c_eff, c_rate = st.columns(3)
dur_delta = c_dur.number_input(
    "Schedule Impact (+/- Days)",
    value=float(existing_adj.get("duration_delta_days", 0.0)),
    step=0.5,
    key=f"dur_{target_task}_{parse_sig}",
)
eff_delta = c_eff.number_input(
    "Effort Impact (+/- Hours)",
    value=float(existing_adj.get("effort_delta_hours", 0.0)),
    step=4.0,
    key=f"eff_{target_task}_{parse_sig}",
)
rate_override_raw = c_rate.number_input(
    "Blended Daily Rate Override (USD, 0 = Current)",
    min_value=0.0,
    value=float(existing_adj.get("daily_rate_override") or 0.0),
    step=50.0,
    key=f"rate_{target_task}_{parse_sig}",
)
rate_override = rate_override_raw if rate_override_raw > 0 else None

if st.button("Run Impact Assessment", type="primary"):
    try:
        sim_res = simulate_change_request(
            base_df=plan_df,
            task_adjustments={
                target_task: {
                    "duration_delta_days": dur_delta,
                    "effort_delta_hours": eff_delta,
                    "daily_rate_override": rate_override,
                    "extra_predecessors": existing_adj.get("extra_predecessors", []),
                }
            },
            new_tasks=parsed_cr.get("new_tasks", []),
            scenario_name=f"CR Simulation ({target_task}: {dur_delta:+.1f}d, {eff_delta:+.0f}h)",
        )
        st.session_state["sim_result"] = sim_res
    except Exception as exc:
        st.error(f"Simulation error: {exc}")

if "sim_result" in st.session_state:
    sim_res = st.session_state["sim_result"]
    deltas = sim_res["deltas"]
    sim_summary = sim_res["simulated"]

    st.subheader(f"Change Impact Assessment: {sim_res['scenario_name']}")
    m1, m2, m3, m4 = st.columns(4)
    dur_d = deltas["project_duration_delta_days"]
    cost_d = deltas["total_cost_delta_usd"]
    m1.metric(
        "Projected Critical Path",
        f"{sim_summary['project_duration_days']:.0f} days",
        delta="0 days" if dur_d == 0 else f"{dur_d:+.1f} days",
        delta_color="off" if dur_d == 0 else "inverse",
    )
    m2.metric(
        "Projected Budget",
        f"${sim_summary['total_baseline_cost_usd']:,.2f}",
        delta="$0.00" if cost_d == 0 else f"${cost_d:+,.2f}",
        delta_color="off" if cost_d == 0 else "inverse",
    )
    m3.metric(
        "Projected Effort",
        f"{sim_summary['total_effort_hours']:,.0f} hrs",
        delta=f"{deltas['total_effort_delta_hours']:+.0f} hrs",
        delta_color="inverse",
    )
    m4.metric(
        "Critical Path Tasks",
        sim_summary["critical_task_count"],
    )

    st.write("**Simulated Critical Path:**", " -> ".join(sim_summary["critical_path_tasks"]))
    st.dataframe(sim_summary["schedule_df"], use_container_width=True, hide_index=True)

    st.subheader("4. Change Advisory Board (CAB) Sign-Off")
    decision = st.radio(
        "CAB Decision:",
        options=["Pending Review", "Approve CR & Baseline Update", "Hold for Scope / Cost Trade-Off", "Reject CR"],
        horizontal=True,
    )
    reviewer_notes = st.text_input("Executive Rationale / Approval Conditions:", placeholder="e.g., Requires client sign-off on +4d schedule shift and cost delta.")
    if st.button("Log CAB Decision"):
        st.success(f"Recorded status: **{decision}** | Scenario: **{sim_res['scenario_name']}** | Notes: {reviewer_notes or 'None'}")
