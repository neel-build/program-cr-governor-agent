# Program CR Governor Agent

**Deterministic Change Impact & Delivery Simulation for Enterprise SaaS Programs**

`program-cr-governor-agent` is a lightweight program governance and delivery simulation application built for enterprise SaaS implementations. It pairs **natural-language Change Request (CR) interpretation** with **deterministic dependency, critical-path, and cost simulation** and **human-in-the-loop review** prior to approving baseline changes.

## Architectural Separation of Concerns

1. **AI for Language Interpretation Only (`src/cr_interpreter.py`):** Uses Gemini (`gemini-2.5-flash` via `google-genai` with structured Pydantic output, plus a deterministic rule-based fallback when no API key is provided) to extract candidate task adjustments from plain-English Change Requests.
2. **Deterministic Math for Schedule & Cost (`src/baseline_engine.py`, `src/schedule_engine.py`, `src/simulation_engine.py`):** Uses **Pandas** and **NetworkX** Directed Acyclic Graphs (DAGs) to validate dependencies, run forward/backward pass Critical Path Method (CPM) calculations, and compute exact schedule, effort, and cost deltas.
3. **Human-in-the-Loop Governance (`app.py`):** Lets a program manager inspect and adjust parsed parameters before simulating and record an explicit governance decision (`Approve`, `Hold for Scope / Cost Trade-Off`, or `Reject`).

## Project Structure

- `app.py` — Streamlit dashboard & human-in-the-loop workflow
- `requirements.txt` — Free-tier Python dependencies
- `data/sample_project_plan.csv` — Synthetic 12-task enterprise SaaS delivery plan
- `src/baseline_engine.py` — CSV schema validation & baseline cost/effort math
- `src/schedule_engine.py` — NetworkX DAG validation & CPM critical-path engine
- `src/simulation_engine.py` — Deterministic CR delta & scenario simulation engine
- `src/cr_interpreter.py` — Gemini structured CR parser + deterministic fallback
- `tests/test_baseline_engine.py` — Unit tests for validation and baseline math
- `tests/test_simulation_and_schedule.py` — Unit tests for CPM schedule, cycles, CR deltas, and parser

## Running Locally or in GitHub Codespaces

```bash
pip install -r requirements.txt
pytest -v
streamlit run app.py