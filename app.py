import pandas as pd
import streamlit as st
from src.baseline_engine import compute_baseline_metrics, validate_project_plan

st.set_page_config(
    page_title="Program CR Governor Agent",
    layout="wide",
)

st.title("Program CR Governor Agent")
st.caption("Deterministic Change Impact & Delivery Simulation for Enterprise SaaS Programs")

st.sidebar.header("1. Project Plan Input")
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

if df is None:
    st.info("Upload a project plan CSV in the sidebar or select the sample SaaS plan to begin.")
    st.stop()

is_valid, errors = validate_project_plan(df)
if not is_valid:
    st.error("Project plan validation failed:")
    for err in errors:
        st.write(f"- {err}")
    st.stop()

plan_df, summary = compute_baseline_metrics(df)

st.subheader("Baseline Project Summary")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Tasks", summary["total_tasks"])
col2.metric("Total Effort", f"{summary['total_effort_hours']:,.0f} hrs")
col3.metric("Total Task Days", f"{summary['total_task_days']:,.0f} days")
col4.metric("Baseline Cost", f"${summary['total_baseline_cost_usd']:,.2f}")

st.subheader("Baseline Task Breakdown")
st.dataframe(plan_df, use_container_width=True, hide_index=True)
