ALLOWED_FILTER_OPS = {"=", "!=", ">", ">=", "<", "<="}

def build_sql(plan: dict, schema: dict) -> str:
    """
    Convert a validated planner JSON into SQL.
    """
    table = schema["table"]
    metric = plan["metric"]
    group_by = plan.get("group_by", [])
    time_range = plan.get("time_range")

    # ----------------------------
    # Metric mapping
    # ----------------------------
    metric_def = schema["metrics"].get(metric)
    if not metric_def:
        raise ValueError(f"Unsupported metric in SQL builder: {metric}")

    column = metric_def["column"]
    aggregation = metric_def["aggregations"][0]

    if aggregation == "avg":
        metric_expr = f"AVG({column}) AS {metric}"
    elif aggregation == "sum":
        metric_expr = f"SUM({column}) AS {metric}"
    elif aggregation == "count":
        metric_expr = "COUNT(*) AS trip_count"
    else:
        raise ValueError(f"Unsupported aggregation: {aggregation}")

    # ----------------------------
    # Group-by handling
    # ----------------------------
    group_columns = []
    for dim in group_by:
        group_columns.append(schema["dimensions"][dim]["column"])

    if group_columns:
        select_clause = ", ".join(group_columns + [metric_expr])
    else:
        select_clause = metric_expr

    # ----------------------------
    # Time filtering
    # ----------------------------
    time_column = schema["time"]["column"]
    where_clause = ""

    if time_range == "last_month":
        where_clause = f"""
        {time_column} = (
            SELECT MAX({time_column}) FROM {table}
        )
        """
    elif time_range == "last_3_months":
        where_clause = f"""
        {time_column} >= (
            SELECT MAX({time_column}) FROM {table}
        )
        """
    elif time_range:
        raise ValueError(f"Unsupported time_range: {time_range}")

    # ----------------------------
    # Final SQL assembly
    # ----------------------------
    sql = f"""
    SELECT {select_clause}
    FROM {table}
    """

    if where_clause:
        sql += f"\nWHERE {where_clause}"

    if group_columns:
        sql += f"\nGROUP BY {', '.join(group_columns)}"

    return sql.strip()
