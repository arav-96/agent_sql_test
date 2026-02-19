# diagnostic.executor - made changes to make it compatible with healthcare schema
from config.diagnostic_config import (
    PRIMARY_EXPANSION_THRESHOLD,
    CONTRIBUTION_THRESHOLD,
)

from tools.rolling_baseline import compare_to_rolling_baseline


class DiagnosticExecutor:

    def __init__(self, schema, sql_executor):
        self.schema = schema
        self.executor = sql_executor
        self.con = self.executor.get_connection()
        self.table = schema.get("table_name", schema.get("table", "claims"))
        self.time_column = schema.get("time", {}).get("column", "year_month")
        self.metrics = schema.get("metrics", {}) if isinstance(schema.get("metrics", {}), dict) else {}
        raw_dimensions = schema.get("dimensions", {})
        self.dimensions = raw_dimensions if isinstance(raw_dimensions, dict) else {}

        self.metric_aliases = {
            "hitrate": "hit_rate" if "hit_rate" in self.metrics else "hitrate",
            "jhitrate": "hit_rate" if "hit_rate" in self.metrics else "jhitrate",
            "avg_savings": "average_savings" if "average_savings" in self.metrics else "avg_savings",
            "claim_count": "audit_volume" if "audit_volume" in self.metrics else "claim_count",
            "audits": "audit_volume" if "audit_volume" in self.metrics else "audits",
        }

        preferred_drill_dimensions = [
            "selection_reason",
            "CC_mcc_type",
            "drg_code",
            "mdc_code",
            "mode",
            "provider_name",
            "mdcn_desc",
            "drg_desc",
            "cc_mcc_type",
            "drg_condition",
            "audit_type",
        ]
        self.drill_dimensions = [d for d in preferred_drill_dimensions if d in self.dimensions]

    def run(self, plan: dict) -> dict:
        metric = self._canonical_metric(plan.get("metric"))

        # Backward-compatible taxi diagnostic flow used by tests.
        if self.table == "taxi_analysis_ready":
            return self._run_taxi_diagnostic(plan)

        if metric == "savings":
            return self._run_savings_tree(plan)

        if metric in self.metrics:
            return self._run_secondary_tree(metric)

        return {}

    def _run_taxi_diagnostic(self, plan: dict) -> dict:
        metric_name = plan.get("metric", "avg_fare")
        metric_map = {
            "avg_fare": "AVG(fare_amount)",
            "total_fare": "SUM(fare_amount)",
            "avg_trip_distance": "AVG(trip_distance)",
            "trip_count": "COUNT(*)",
        }
        metric_expr = metric_map.get(metric_name, "AVG(fare_amount)")

        period_comparison_sql = f"""
            WITH monthly AS (
                SELECT year_month, {metric_expr} AS metric_value
                FROM {self.table}
                GROUP BY year_month
            ),
            curr AS (
                SELECT year_month, metric_value
                FROM monthly
                ORDER BY year_month DESC
                LIMIT 1
            ),
            prev AS (
                SELECT AVG(metric_value) AS baseline_avg
                FROM (
                    SELECT metric_value
                    FROM monthly
                    ORDER BY year_month DESC
                    OFFSET 1
                    LIMIT 3
                ) t
            )
            SELECT
                curr.year_month AS current_month,
                curr.metric_value AS current_value,
                prev.baseline_avg,
                CASE
                    WHEN prev.baseline_avg IS NULL OR prev.baseline_avg = 0 THEN 0
                    ELSE (curr.metric_value - prev.baseline_avg) / prev.baseline_avg
                END AS pct_change
            FROM curr, prev
        """

        top_contributors_sql = f"""
            SELECT VendorID AS segment, {metric_expr} AS value
            FROM {self.table}
            WHERE year_month = (
                SELECT MAX(year_month) FROM {self.table}
            )
            GROUP BY VendorID
            ORDER BY value DESC
            LIMIT 5
        """

        period_rows = self.con.execute(period_comparison_sql).fetchall()
        period = {}
        if period_rows:
            row = period_rows[0]
            period = {
                "current_month": row[0],
                "current_value": float(row[1]) if row[1] is not None else None,
                "baseline_avg": float(row[2]) if row[2] is not None else None,
                "pct_change": float(row[3]) if row[3] is not None else 0.0,
            }

        contributors_df = self.executor.execute(top_contributors_sql)
        top_contributors = [
            {"segment": row["segment"], "value": float(row["value"])}
            for _, row in contributors_df.iterrows()
        ]

        return {
            "period_comparison": period,
            "top_contributors": top_contributors,
        }

    def _canonical_metric(self, metric_name: str):
        if metric_name in self.metrics:
            return metric_name
        return self.metric_aliases.get(metric_name, metric_name)

    def _resolve_metric_expr(self, metric_name: str):
        metric_def = self.metrics.get(metric_name)
        if not metric_def:
            return None

        aggregation = (metric_def.get("aggregations") or [None])[0]
        column = metric_def.get("column", "*")
        if aggregation == "sum":
            return f"SUM({column})"
        if aggregation == "avg":
            return f"AVG({column})"
        if aggregation == "count":
            return "COUNT(*)" if column == "*" else f"COUNT({column})"
        if aggregation == "custom":
            return metric_def.get("expression")
        return None

    def _metric_series_sql(self, metric_name: str):
        metric_expr = self._resolve_metric_expr(metric_name)
        if not metric_expr:
            return None
        return f"""
            SELECT {self.time_column} AS year_month,
                   {metric_expr} AS value
            FROM {self.table}
            GROUP BY {self.time_column}
        """

    def _secondary_metrics_from_plan(self, plan: dict):
        steps = plan.get("analysis_steps", [])
        requested = []
        if isinstance(steps, list):
            for step in steps:
                if isinstance(step, str) and step.startswith("check_secondary_metric:"):
                    _, metric_name = step.split(":", 1)
                    canonical = self._canonical_metric(metric_name)
                    if canonical in self.metrics and canonical not in requested and canonical != "savings":
                        requested.append(canonical)

        if requested:
            return requested

        preferred_secondary = [
            "audit_volume",
            "average_savings",
            "hit_rate",
            "audits",
            "avg_savings",
            "selections",
            "rejection_rate",
        ]
        return [self._canonical_metric(m) for m in preferred_secondary if self._canonical_metric(m) in self.metrics]

    def _run_savings_tree(self, plan: dict):
        primary_sql = self._metric_series_sql("savings")
        if not primary_sql:
            return {
                "primary_metric": {},
                "primary_dimension_drilldowns": {},
                "secondary_metrics": {},
            }
        primary = compare_to_rolling_baseline(self.con, primary_sql)

        result = {
            "primary_metric": primary,
            "primary_dimension_drilldowns": {},
            "secondary_metrics": {},
        }

        if abs(primary.get("pct_change", 0)) >= PRIMARY_EXPANSION_THRESHOLD:
            # First drill down on the primary metric (savings) to answer "why savings changed".
            for dimension in self.drill_dimensions:
                drill = self._compute_dimension_contribution("savings", dimension)
                if drill:
                    result["primary_dimension_drilldowns"][dimension] = drill

            # Then evaluate secondary metrics.
            for metric in self._secondary_metrics_from_plan(plan):
                result["secondary_metrics"][metric] = self._run_secondary_tree(metric)

        return result

    def _run_secondary_tree(self, metric_name):
        canonical_metric = self._canonical_metric(metric_name)
        metric_sql = self._metric_series_sql(canonical_metric)
        if not metric_sql:
            return {"baseline": {}, "dimension_drilldowns": {}}

        baseline = compare_to_rolling_baseline(self.con, metric_sql)

        result = {"baseline": baseline, "dimension_drilldowns": {}}

        if abs(baseline.get("pct_change", 0)) >= PRIMARY_EXPANSION_THRESHOLD:
            for dimension in self.drill_dimensions:
                drill = self._compute_dimension_contribution(canonical_metric, dimension)
                if drill:
                    result["dimension_drilldowns"][dimension] = drill

        return result

    def _compute_dimension_contribution(self, metric_name, dimension):
        dim_def = self.dimensions.get(dimension, {})
        dim_column = dim_def.get("column", dimension)

        current_month_sql = f"""
            SELECT {self.time_column}
            FROM {self.table}
            GROUP BY {self.time_column}
            ORDER BY {self.time_column} DESC
            LIMIT 1
        """

        current_month = self.con.execute(current_month_sql).fetchone()[0]
        metric_expr = self._resolve_metric_expr(metric_name)
        if not metric_expr:
            return None

        current_sql = f"""
            SELECT {dim_column} AS dim,
                   {metric_expr} AS value
            FROM {self.table}
            WHERE {self.time_column} = '{current_month}'
            GROUP BY {dim_column}
        """

        df = self.executor.execute(current_sql)
        if df.empty:
            return None

        total_value = df["value"].sum()
        material_segments = []

        for _, row in df.iterrows():
            contribution = row["value"] / total_value if total_value != 0 else 0
            if abs(contribution) >= CONTRIBUTION_THRESHOLD:
                material_segments.append(
                    {"segment": row["dim"], "contribution": float(contribution)}
                )

        return material_segments if material_segments else None
