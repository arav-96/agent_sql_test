# planner_runner - modified to work for healthcare data
import json
import os
from typing import Optional

from openai import AzureOpenAI

from prompts.planner_prompt import build_planner_prompt
from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA

api_key = os.environ.get("azure_api_key")
azure_endpoint = os.environ.get("azure_endpoint")


def _build_client():
    return AzureOpenAI(api_key=api_key, api_version="2024-12-01-preview", azure_endpoint=azure_endpoint)


def _schema_metric_keys(schema: dict) -> set[str]:
    metrics = schema.get("metrics", {})
    if isinstance(metrics, dict):
        return set(metrics.keys())
    if isinstance(metrics, (list, set, tuple)):
        return set(metrics)
    return set()


def _schema_dimension_keys(schema: dict) -> set[str]:
    dimensions = schema.get("dimensions", {})
    if isinstance(dimensions, dict):
        return set(dimensions.keys())
    if isinstance(dimensions, (list, set, tuple)):
        return set(dimensions)
    return set()


def _pick_existing(schema_keys: set[str], options: list[str]) -> str | None:
    for option in options:
        if option in schema_keys:
            return option
    return None


def normalize_plan(plan: dict, schema: dict) -> dict:
    metric_keys = _schema_metric_keys(schema)
    dimension_keys = _schema_dimension_keys(schema)

    metric_aliases = {
        "hitrate": ["hitrate", "hit_rate", "jhitrate"],
        "hit_rate": ["hit_rate", "hitrate", "jhitrate"],
        "jhitrate": ["jhitrate", "hitrate", "hit_rate"],
        "selection": ["selections", "selection"],
        "selections": ["selections", "selection"],
        "rejection": ["rejections", "rejection_rate", "rejection"],
        "rejections": ["rejections", "rejection_rate", "rejection"],
        "inscope_to_selections": ["inscope_to_selections", "inscope_to_selection"],
        "inscope_to_selection": ["inscope_to_selection", "inscope_to_selections"],
    }

    dimension_aliases = {"mdoe": "mode"}

    normalized = dict(plan)
    raw_metric = str(normalized.get("metric", ""))
    metric_options = metric_aliases.get(raw_metric, [raw_metric])
    selected_metric = _pick_existing(metric_keys, metric_options)
    if selected_metric:
        normalized["metric"] = selected_metric

    group_by = normalized.get("group_by", [])
    if isinstance(group_by, list):
        fixed_group = []
        for dim in group_by:
            candidate = dimension_aliases.get(dim, dim)
            if candidate in dimension_keys:
                fixed_group.append(candidate)
        normalized["group_by"] = fixed_group

    filters = normalized.get("filters", [])
    if isinstance(filters, list):
        fixed_filters = []
        for flt in filters:
            if not isinstance(flt, dict):
                fixed_filters.append(flt)
                continue
            fixed = dict(flt)
            field = fixed.get("field")
            if field in dimension_aliases:
                fixed["field"] = dimension_aliases[field]
            if fixed.get("field") == "audit_type" and isinstance(fixed.get("value"), str):
                value = fixed["value"].strip().lower()
                if value in {"coding", "msdrg"}:
                    fixed["value"] = "MSDRG"
                elif value in {"cva", "clinical", "drgcl"}:
                    fixed["value"] = "DRGCL"
                else:
                    fixed["value"] = "whole"
            fixed_filters.append(fixed)
        normalized["filters"] = fixed_filters

    analysis_steps = normalized.get("analysis_steps", [])
    if isinstance(analysis_steps, list):
        fixed_steps = []
        for step in analysis_steps:
            if step.startswith("check_secondary_metric:"):
                metric_name = step.split(":", 1)[1]
                metric_options = metric_aliases.get(metric_name, [metric_name])
                metric_name = _pick_existing(metric_keys, metric_options) or metric_name
                fixed_steps.append(f"check_secondary_metric:{metric_name}")
                continue
            if step.startswith("drill_by_dimension:"):
                dim_name = step.split(":", 1)[1]
                dim_name = dimension_aliases.get(dim_name, dim_name)
                fixed_steps.append(f"drill_by_dimension:{dim_name}")
                continue
            fixed_steps.append(step)
        normalized["analysis_steps"] = fixed_steps

    return normalized


def run_planner(user_question: str, schema: Optional[dict] = None) -> dict:
    active_schema = schema or HEALTHCARE_CLAIMS_SCHEMA
    messages = build_planner_prompt(schema=active_schema, user_question=user_question)

    if not api_key or not azure_endpoint:
        return {
            "error": "MISSING_AZURE_CONFIG",
            "error_type": "CONFIG",
            "message": "Set azure_api_key and azure_endpoint environment variables.",
            "question": user_question,
        }

    client = _build_client()

    try:
        response = client.chat.completions.create(model="gpt-4.1-mini", messages=messages, temperature=0.0, max_tokens=300)
        content = response.choices[0].message.content
        parsed = json.loads(content)
        return normalize_plan(parsed, active_schema) if isinstance(parsed, dict) else parsed
    except Exception as e:
        error_name = e.__class__.__name__
        if error_name == "BadRequestError":
            return {"error": "CONTENT_FILTERED", "error_type": "AZURE_POLICY", "message": str(e), "question": user_question}
        if isinstance(e, json.JSONDecodeError):
            return {"error": "INVALID_JSON", "error_type": "PARSER", "raw_output": content, "question": user_question}
        return {"error": "PLANNER_RUNTIME_ERROR", "error_type": error_name, "message": str(e), "question": user_question}
