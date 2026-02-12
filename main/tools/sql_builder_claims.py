ALLOWED_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<=", "LIKE", "IN"}


def build_claims_sql(plan: dict, schema: dict) -> str:
    """
    Build a claims SQL query from a semantic plan.
    """
    table = schema["table"]
    metric_key = plan["metric"]
    metric_def = schema["metrics"].get(metric_key)
    if not metric_def:
        raise ValueError(f"Unsupported metric: {metric_key}")

    group_by_dims = plan.get("group_by", [])
    time_range = plan.get("time_range", "current_month")
    filters = plan.get("filters", [])

    metric_expr = _build_metric_expr(metric_key, metric_def)
    group_columns = _build_group_columns(group_by_dims, schema)
    where_conditions = _build_filter_conditions(filters)

    time_column = schema["time"]["column"]
    time_filter = _get_time_filter(table, time_column, time_range)
    if time_filter:
        where_conditions.append(time_filter)

    select_parts = group_columns + [metric_expr]
    sql = f"SELECT {', '.join(select_parts)}\nFROM {table}"
    if where_conditions:
        sql += "\nWHERE " + " AND ".join(where_conditions)
    if group_columns:
        sql += "\nGROUP BY " + ", ".join(group_columns)
    return sql


def _build_metric_expr(metric_key: str, metric_def: dict) -> str:
    aggregation = metric_def["aggregations"][0]
    column = metric_def["column"]
    if aggregation == "custom":
        return f"{metric_def['expression']} AS {metric_key}"
    if aggregation == "avg":
        return f"AVG({column}) AS {metric_key}"
    if aggregation == "sum":
        return f"SUM({column}) AS {metric_key}"
    if aggregation == "count":
        if column == "*":
            return f"COUNT(*) AS {metric_key}"
        return f"COUNT({column}) AS {metric_key}"
    raise ValueError(f"Unsupported aggregation: {aggregation}")


def _build_group_columns(group_by_dims: list[str], schema: dict) -> list[str]:
    columns = []
    for dim in group_by_dims:
        dim_def = schema["dimensions"].get(dim)
        if not dim_def:
            raise ValueError(f"Unknown dimension: {dim}")
        columns.append(dim_def["column"])
    return columns


def _build_filter_conditions(filters: list[dict]) -> list[str]:
    conditions = []
    for f in filters:
        column = f["column"]
        op = f["op"]
        value = f["value"]

        if op not in ALLOWED_FILTER_OPS:
            raise ValueError(f"Unsupported filter operation: {op}")

        if op == "IN":
            if not isinstance(value, (list, tuple)) or not value:
                raise ValueError("IN filter value must be a non-empty list or tuple")
            values = [f"'{v}'" if isinstance(v, str) else str(v) for v in value]
            conditions.append(f"{column} IN ({', '.join(values)})")
            continue

        if isinstance(value, str):
            conditions.append(f"{column} {op} '{value}'")
        else:
            conditions.append(f"{column} {op} {value}")
    return conditions


def _get_time_filter(table: str, time_column: str, time_range: str) -> str:
    max_month = f"(SELECT MAX({time_column}) FROM {table})"
    if time_range == "current_month":
        return f"{time_column} = {max_month}"
    if time_range == "last_month":
        return f"{time_column} = ({max_month} - 1)"
    if time_range == "last_3_months":
        return f"{time_column} >= ({max_month} - 2)"
    if time_range == "last_6_months":
        return f"{time_column} >= ({max_month} - 5)"
    if time_range == "last_12_months":
        return f"{time_column} >= ({max_month} - 11)"
    return ""
