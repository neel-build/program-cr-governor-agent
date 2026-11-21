import json
import os
import re
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class TaskAdjustmentSpec(BaseModel):
    task_id: str = Field(description="Target task_id from the project plan, e.g. T05")
    duration_delta_days: float = Field(default=0.0, description="Change in duration in days (positive to extend, negative to compress)")
    effort_delta_hours: float = Field(default=0.0, description="Change in effort hours (positive to add effort, negative to reduce)")
    daily_rate_override: float | None = Field(default=None, description="Optional replacement daily rate in USD")
    extra_predecessors: list[str] = Field(default_factory=list, description="Optional additional predecessor task_ids")


class NewTaskSpec(BaseModel):
    task_id: str = Field(description="New unique task_id such as T13")
    task_name: str = Field(description="Short descriptive name for the new task")
    phase: str = Field(default="Build", description="Project phase such as Discovery, Design, Build, Test, UAT, Release, Hypercare")
    predecessors: list[str] = Field(default_factory=list, description="List of predecessor task_ids")
    duration_days: float = Field(default=1.0, description="Task duration in days")
    effort_hours: float = Field(default=8.0, description="Task effort in hours")
    daily_rate_usd: float = Field(default=700.0, description="Daily rate in USD")


class ParsedChangeRequest(BaseModel):
    scenario_title: str = Field(description="Concise title for the change request scenario")
    rationale: str = Field(description="Brief interpretation of how the change request maps to plan tasks")
    adjustments: list[TaskAdjustmentSpec] = Field(default_factory=list)
    new_tasks: list[NewTaskSpec] = Field(default_factory=list)


def _fallback_rule_parse(cr_text: str, valid_task_ids: list[str]) -> dict:
    """Deterministic fallback parser when GEMINI_API_KEY is not present."""
    text = cr_text.strip()
    upper_ids = [tid.upper() for tid in valid_task_ids]
    found_ids = []
    for match in re.findall(r"\b[Tt]\d+\b", text):
        cid = match.upper()
        if cid in upper_ids and cid not in found_ids:
            found_ids.append(cid)

    if not found_ids and upper_ids:
        # Default to T05 if mentioned by keyword, else first task
        if "billing" in text.lower() or "erp" in text.lower() or "api" in text.lower():
            found_ids = ["T05"] if "T05" in upper_ids else [upper_ids[0]]
        else:
            found_ids = [upper_ids[0]]

    days_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(?:day|days|d)\b", text, re.IGNORECASE)
    hours_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*(?:hour|hours|hr|hrs|h)\b", text, re.IGNORECASE)

    dur_delta = float(days_match.group(1)) if days_match else 3.0
    eff_delta = float(hours_match.group(1)) if hours_match else dur_delta * 8.0

    task_adjustments = {
        tid: {
            "duration_delta_days": dur_delta,
            "effort_delta_hours": eff_delta,
            "daily_rate_override": None,
            "extra_predecessors": [],
        }
        for tid in found_ids
    }

    return {
        "scenario_title": f"CR Simulation ({', '.join(found_ids)})",
        "rationale": (
            f"Parsed via deterministic fallback mode (no GEMINI_API_KEY set): "
            f"applied {dur_delta:+.1f} days and {eff_delta:+.1f} hours to {', '.join(found_ids)}."
        ),
        "task_adjustments": task_adjustments,
        "new_tasks": [],
        "source": "deterministic_fallback",
    }


def interpret_change_request(
    cr_text: str,
    valid_task_ids: list[str],
    api_key: str | None = None,
) -> dict:
    """
    Interpret a natural-language change request using Gemini (free-tier model)
    with structured output, or fall back cleanly if no API key is configured.
    """
    if not cr_text or not cr_text.strip():
        raise ValueError("Change request description cannot be empty.")

    effective_key = (api_key or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not effective_key:
        return _fallback_rule_parse(cr_text, valid_task_ids)

    client = genai.Client(api_key=effective_key)
    prompt = (
        "You are a technical program governance assistant. Parse the following Change Request (CR) "
        "into structured schedule/effort/cost adjustments for an enterprise SaaS project plan.\n"
        f"Valid task_ids in the plan: {', '.join(valid_task_ids)}\n"
        "Only reference valid task_ids for adjustments or extra_predecessors. "
        "Do not calculate project totals or critical paths yourself—only extract change inputs.\n\n"
        f"Change Request:\n{cr_text.strip()}"
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParsedChangeRequest,
                temperature=0.1,
            ),
        )
    except Exception as exc:
        fallback = _fallback_rule_parse(cr_text, valid_task_ids)
        fallback["rationale"] = f"Gemini unavailable ({type(exc).__name__}); {fallback.get("rationale", "used deterministic rule parser.")}"
        return fallback

    parsed: ParsedChangeRequest = response.parsed
    task_adjustments = {}
    valid_set = {str(t).strip() for t in valid_task_ids}

    for adj in parsed.adjustments:
        tid = adj.task_id.strip()
        if tid in valid_set:
            clean_preds = [p.strip() for p in adj.extra_predecessors if p.strip() in valid_set and p.strip() != tid]
            task_adjustments[tid] = {
                "duration_delta_days": float(adj.duration_delta_days),
                "effort_delta_hours": float(adj.effort_delta_hours),
                "daily_rate_override": float(adj.daily_rate_override) if adj.daily_rate_override is not None else None,
                "extra_predecessors": clean_preds,
            }

    new_tasks_list = []
    for nt in parsed.new_tasks:
        clean_preds = [p.strip() for p in nt.predecessors if p.strip() in valid_set]
        new_tasks_list.append(
            {
                "task_id": nt.task_id.strip(),
                "task_name": nt.task_name.strip(),
                "phase": nt.phase.strip(),
                "predecessors": clean_preds,
                "duration_days": float(nt.duration_days),
                "effort_hours": float(nt.effort_hours),
                "daily_rate_usd": float(nt.daily_rate_usd),
            }
        )

    return {
        "scenario_title": parsed.scenario_title,
        "rationale": parsed.rationale,
        "task_adjustments": task_adjustments,
        "new_tasks": new_tasks_list,
        "source": "gemini-3.8-flash",
    }
