from typing import Dict, List, Set


# ---- Allowed analysis steps (STRICT ENUM) ----
ALLOWED_ANALYSIS_STEPS: Set[str] = {
    "compare_previous_period",
    "drill_by_vendor",
    "drill_by_pickup_location",
    "drill_by_time",
    "rank_top_contributors",
    "check_related_metric:avg_trip_distance"
}


def validate_plan(plan: Dict, schema: Dict) -> List[str]:
    """
    Validates planner output against schema and safety rules.

    Returns:
        List[str]: A list of validation error messages.
                   Empty list means the plan is valid.
    """
    errors: List[str] = []

    # ----------------------------
    # 1. Basic shape validation
    # ----------------------------
    required_keys = {
        "intent",
        "metric",
        "time_range",
        "group_by",
        "filters",
        "analysis_steps"
    }

    missing_keys = required_keys - plan.keys()
    if missing_keys:
        errors.append(f"Missing required keys: {missing_keys}")
        # If shape is wrong, stop early
        return errors

    # ----------------------------
    # 2. Intent validation
    # ----------------------------
    intent = plan.get("intent")
    if intent not in {"descriptive", "diagnostic"}:
        errors.append(f"Invalid intent: {intent}")

    # ----------------------------
    # 3. Metric validation (CRITICAL)
    # ----------------------------
    metric = plan.get("metric", "")

    if metric == "":
        # Empty metric is allowed only for vague / fallback cases
        pass

    elif metric == "UNSUPPORTED_METRIC":
        # Explicitly allowed and EXPECTED for evil prompts
        pass

    elif metric not in schema["metrics"]:
        # Anything else is a hallucination
        errors.append(f"Invalid metric (hallucinated): {metric}")

    # ----------------------------
    # 4. Time range validation
    # ----------------------------
    time_range = plan.get("time_range", "")

    if time_range:
        supported_ranges = schema["time"]["supported_ranges"]
        if time_range not in supported_ranges:
            errors.append(f"Invalid time_range: {time_range}")

    # ----------------------------
    # 5. Group-by validation
    # ----------------------------
    group_by = plan.get("group_by", [])

    if not isinstance(group_by, list):
        errors.append("group_by must be a list")

    else:
        for dim in group_by:
            if dim not in schema["dimensions"]:
                errors.append(f"Invalid group_by dimension: {dim}")

    # ----------------------------
    # 6. Analysis steps validation
    # ----------------------------
    analysis_steps = plan.get("analysis_steps", [])

    if not isinstance(analysis_steps, list):
        errors.append("analysis_steps must be a list")

    else:
        for step in analysis_steps:
            if step not in ALLOWED_ANALYSIS_STEPS:
                errors.append(f"Invalid analysis_step: {step}")

    # ----------------------------
    # 7. Filters validation (basic)
    # ----------------------------
    filters = plan.get("filters", [])

    if not isinstance(filters, list):
        errors.append("filters must be a list")

    # (You can add stricter filter validation later)

    return errors
