from typing import Dict, List, Set


ALLOWED_BASE_ANALYSIS_STEPS: Set[str] = {
    "compare_previous_period",
    "rank_top_contributors",
    "drill_by_category",
    "drill_by_subprogram",
    "drill_by_provider",
    "drill_by_time",
}

ALLOWED_FILTER_OPS: Set[str] = {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IN"}


def validate_plan_claims(plan: Dict, schema: Dict) -> List[str]:
    """
    Validates claims planner output against claims schema and safety rules.

    Returns:
        List[str]: validation error messages; empty means valid.
    """
    errors: List[str] = []

    required_keys = {
        "intent",
        "metric",
        "time_range",
        "group_by",
        "filters",
        "analysis_steps",
    }

    missing_keys = required_keys - plan.keys()
    if missing_keys:
        errors.append(f"Missing required keys: {missing_keys}")
        return errors

    intent = plan.get("intent")
    if intent not in {"descriptive", "diagnostic"}:
        errors.append(f"Invalid intent: {intent}")

    metric = plan.get("metric", "")
    if metric == "":
        pass
    elif metric == "UNSUPPORTED_METRIC":
        pass
    elif metric not in schema["metrics"]:
        errors.append(f"Invalid metric (hallucinated): {metric}")

    time_range = plan.get("time_range", "")
    if time_range:
        supported_ranges = schema["time"]["supported_ranges"]
        if time_range not in supported_ranges:
            errors.append(f"Invalid time_range: {time_range}")

    group_by = plan.get("group_by", [])
    if not isinstance(group_by, list):
        errors.append("group_by must be a list")
    else:
        for dim in group_by:
            if dim not in schema["dimensions"]:
                errors.append(f"Invalid group_by dimension: {dim}")

    analysis_steps = plan.get("analysis_steps", [])
    if not isinstance(analysis_steps, list):
        errors.append("analysis_steps must be a list")
    else:
        for step in analysis_steps:
            if step in ALLOWED_BASE_ANALYSIS_STEPS:
                continue

            if step.startswith("check_related_metric:"):
                related_metric = step.split(":", 1)[1]
                if related_metric not in schema["metrics"]:
                    errors.append(f"Invalid related metric in analysis_step: {step}")
                continue

            errors.append(f"Invalid analysis_step: {step}")

    filters = plan.get("filters", [])
    if not isinstance(filters, list):
        errors.append("filters must be a list")
    else:
        for idx, f in enumerate(filters):
            if not isinstance(f, dict):
                errors.append(f"Filter at index {idx} must be an object")
                continue

            for key in {"column", "op", "value"}:
                if key not in f:
                    errors.append(f"Filter at index {idx} missing key: {key}")

            if "column" in f and f["column"] not in _allowed_filter_columns(schema):
                errors.append(f"Invalid filter column at index {idx}: {f['column']}")

            if "op" in f and f["op"] not in ALLOWED_FILTER_OPS:
                errors.append(f"Invalid filter operation at index {idx}: {f['op']}")

            if f.get("op") == "IN" and not isinstance(f.get("value"), list):
                errors.append(f"IN filter requires a list value at index {idx}")

    return errors


def _allowed_filter_columns(schema: Dict) -> Set[str]:
    dim_columns = {v["column"] for v in schema["dimensions"].values()}
    metric_columns = {
        v["column"] for v in schema["metrics"].values() if v["column"] != "*"
    }
    return dim_columns | metric_columns | {schema["time"]["column"]}
