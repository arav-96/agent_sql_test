# planner_validator - additional changes and cases added
from typing import Dict, List, Set

STATIC_ALLOWED_ANALYSIS_STEPS: Set[str] = {"compare_previous_period","drill_by_time","rank_top_contributors","rank_top_decliners","provider_health_scan"}
ALLOWED_FILTER_OPS: Set[str] = {"=", "!=", ">", ">=", "<", "<="}

def _schema_metric_keys(schema: Dict) -> Set[str]:
    metrics = schema.get("metrics", {})
    if isinstance(metrics, dict):
        return set(metrics.keys())
    if isinstance(metrics, (list, set, tuple)):
        return set(metrics)
    return set()

def _schema_dimension_keys(schema: Dict) -> Set[str]:
    dimensions = schema.get("dimensions", {})
    if isinstance(dimensions, dict):
        return set(dimensions.keys())
    if isinstance(dimensions, (list, set, tuple)):
        return set(dimensions)
    return set()

def _is_allowed_analysis_step(step: str, schema: Dict) -> bool:
    metric_keys = _schema_metric_keys(schema)
    dimension_keys = _schema_dimension_keys(schema)
    if step in STATIC_ALLOWED_ANALYSIS_STEPS:
        return True
    if step.startswith("check_secondary_metric:"):
        return step.split(":", 1)[1] in metric_keys
    if step.startswith("drill_by_dimension:"):
        return step.split(":", 1)[1] in dimension_keys
    if step.startswith("check_related_metric:"):
        return step.split(":", 1)[1] in metric_keys
    if step.startswith("drill_by_"):
        return step[len("drill_by_"):] in dimension_keys
    return False

def validate_plan(plan: Dict, schema: Dict) -> List[str]:
    errors: List[str] = []
    required_keys = {"intent","metric","time_range","group_by","filters","analysis_steps"}
    missing_keys = required_keys - plan.keys()
    if missing_keys:
        errors.append(f"Missing required keys: {missing_keys}")
        return errors

    intent = plan.get("intent")
    if intent not in {"descriptive", "diagnostic"}:
        errors.append(f"Invalid intent: {intent}")

    metric = plan.get("metric", "")
    metric_keys = _schema_metric_keys(schema)
    if metric not in {"", "UNSUPPORTED_METRIC"} and metric not in metric_keys:
        errors.append(f"Invalid metric (hallucinated): {metric}")

    time_range = plan.get("time_range", "")
    supported_ranges = schema.get("time", {}).get("supported_ranges", [])
    if time_range and time_range not in supported_ranges:
        errors.append(f"Invalid time_range: {time_range}")

    group_by = plan.get("group_by", [])
    dimension_keys = _schema_dimension_keys(schema)
    if not isinstance(group_by, list):
        errors.append("group_by must be a list")
    else:
        for dim in group_by:
            if dim not in dimension_keys:
                errors.append(f"Invalid group_by dimension: {dim}")

    analysis_steps = plan.get("analysis_steps", [])
    if not isinstance(analysis_steps, list):
        errors.append("analysis_steps must be a list")
    else:
        for step in analysis_steps:
            if not _is_allowed_analysis_step(step, schema):
                errors.append(f"Invalid analysis_step: {step}")

    filters = plan.get("filters", [])
    if not isinstance(filters, list):
        errors.append("filters must be a list")
    else:
        raw_columns = set(schema.get("raw_columns", []))
        allowed_filter_fields = dimension_keys | raw_columns
        for idx, flt in enumerate(filters):
            if not isinstance(flt, dict):
                errors.append(f"filters[{idx}] must be an object")
                continue
            field = flt.get("field")
            op = flt.get("op")
            if field not in allowed_filter_fields:
                errors.append(f"Invalid filter field: {field}")
            if op not in ALLOWED_FILTER_OPS:
                errors.append(f"Invalid filter operator: {op}")
            if "value" not in flt:
                errors.append(f"filters[{idx}] missing value")

    return errors
