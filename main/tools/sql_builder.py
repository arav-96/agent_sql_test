# sql_builder - modified to work for healthcare data
ALLOWED_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<="}


def _format_value(value):
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    if value is None:
        return "NULL"
    return str(value)


def _resolve_table(schema: dict) -> str:
    table = schema.get("table") or schema.get("table_name")
    if not table:
        raise ValueError("Schema must define either 'table' or 'table_name'")
    return table


def _normalize_dimensions(schema: dict) -> dict:
    dimensions = schema.get("dimensions", {})

    if isinstance(dimensions, dict):
        return dimensions

    if isinstance(dimensions, (list, set, tuple)):
        return {dim: {"column": dim} for dim in dimensions}

    raise ValueError("Schema dimensions must be dict or list")


def _get_metric_def(schema: dict, metric: str):
    metrics = schema.get("metrics", {})

    if isinstance(metrics, dict):
        return metrics.get(metric)

    if isinstance(metrics, (list, set, tuple)):
        if metric not in metrics:
            return None

        # Backward compatibility for healthcare list-style schema.
        try:
            from tools.healthcare_metrics import HEALTHCARE_METRICS

            return HEALTHCARE_METRICS.get(metric)
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise ValueError(
                "List-style schema.metrics requires metric definitions in tools.healthcare_metrics"
            ) from exc

    raise ValueError("Schema metrics must be dict or list")


def _normalize_supported_ranges(schema: dict) -> set:
    supported_ranges = schema.get("time", {}).get("supported_ranges", [])
    if isinstance(supported_ranges, (list, set, tuple)):
        return set(supported_ranges)
    raise ValueError("Schema time.supported_ranges must be list, set, or tuple")


def _build_metric_expression(metric: str, metric_def: dict) -> str:
    if not metric_def:
        raise ValueError(f"Unsupported metric in SQL builder: {metric}")

    column = metric_def.get("column", "*")
    aggregations = metric_def.get("aggregations", [])

    if not aggregations:
        raise ValueError(f"Metric '{metric}' must define at least one aggregation")

    aggregation = aggregations[0]

    if aggregation == "avg":
        return f"AVG({column}) AS {metric}"

    if aggregation == "sum":
        return f"SUM({column}) AS {metric}"

    if aggregation == "count":
        if column == "*":
            return f"COUNT(*) AS {metric}"
        return f"COUNT({column}) AS {metric}"

    if aggregation == "custom":
        expression = metric_def.get("expression")
        if not expression:
            raise ValueError(f"Metric '{metric}' uses custom aggregation but has no expression")
        return f"{expression} AS {metric}"

    raise ValueError(f"Unsupported aggregation: {aggregation}")


def _build_time_condition(table: str, time_column: str, time_range: str) -> str:
    if time_range == "current_month":
        return f"{time_column} = (SELECT MAX({time_column}) FROM {table})"

    if time_range == "last_month":
        return (
            f"{time_column} = (SELECT {time_column} FROM {table} "
            f"GROUP BY {time_column} ORDER BY {time_column} DESC LIMIT 1 OFFSET 1)"
        )

    range_to_limit = {
        "last_3_months": 3,
        "last_6_months": 6,
        "last_12_months": 12,
        "month_over_month": 2,
    }
    if time_range in range_to_limit:
        limit = range_to_limit[time_range]
        return (
            f"{time_column} IN (SELECT {time_column} FROM {table} "
            f"GROUP BY {time_column} ORDER BY {time_column} DESC LIMIT {limit})"
        )

    raise ValueError(f"Unsupported time_range: {time_range}")


def build_sql(plan: dict, schema: dict) -> str:
    """Convert a validated planner JSON into SQL."""
    table = _resolve_table(schema)
    metric = plan["metric"]
    group_by = plan.get("group_by", [])
    time_range = plan.get("time_range")
    filters = plan.get("filters", [])

    if metric == "UNSUPPORTED_METRIC":
        raise ValueError("Planner returned UNSUPPORTED_METRIC; SQL cannot be generated.")

    metric_def = _get_metric_def(schema, metric)
    metric_expr = _build_metric_expression(metric, metric_def)

    normalized_dimensions = _normalize_dimensions(schema)
    group_columns = []
    for dim in group_by:
        dim_def = normalized_dimensions.get(dim)
        if not dim_def:
            raise ValueError(f"Unsupported group_by dimension: {dim}")
        group_columns.append(dim_def["column"])

    select_clause = ", ".join(group_columns + [metric_expr]) if group_columns else metric_expr

    conditions = []
    time_column = schema.get("time", {}).get("column")
    if not time_column:
        raise ValueError("Schema time configuration must define 'column'")

    supported_ranges = _normalize_supported_ranges(schema)
    if time_range:
        if time_range not in supported_ranges:
            raise ValueError(f"Unsupported time_range: {time_range}")
        conditions.append(_build_time_condition(table, time_column, time_range))

    raw_columns = set(schema.get("raw_columns", []))
    allowed_filter_fields = set(normalized_dimensions.keys()) | raw_columns

    for flt in filters:
        field = flt.get("field")
        op = flt.get("op")
        value = flt.get("value")

        if op not in ALLOWED_FILTER_OPS:
            raise ValueError(f"Unsupported filter operator: {op}")

        if field not in allowed_filter_fields:
            raise ValueError(f"Unsupported filter field: {field}")

        if field in normalized_dimensions:
            column_name = normalized_dimensions[field]["column"]
        else:
            column_name = field

        if value is None:
            if op == "=":
                conditions.append(f"{column_name} IS NULL")
                continue
            if op == "!=":
                conditions.append(f"{column_name} IS NOT NULL")
                continue
            raise ValueError(f"Filter value cannot be NULL for operator: {op}")

        conditions.append(f"{column_name} {op} {_format_value(value)}")

    sql = f"""
    SELECT {select_clause}
    FROM {table}
    """

    if conditions:
        sql += "\nWHERE " + "\n  AND ".join(conditions)

    if group_columns:
        sql += f"\nGROUP BY {', '.join(group_columns)}"

    return sql.strip()
