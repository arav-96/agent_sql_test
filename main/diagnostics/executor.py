from tools.sql_builder import build_sql


class DiagnosticExecutor:
    """
    Executes diagnostic analysis steps defined in planner output.
    """

    def __init__(self, schema: dict, sql_executor):
        """
        Args:
            schema: Semantic schema (e.g. TAXI_SEMANTIC_SCHEMA)
            sql_executor: Instance of DuckDBExecutor (or compatible)
        """
        self.schema = schema
        self.sql_executor = sql_executor

    # ---------------------------------------------------------
    # Public entry point
    # ---------------------------------------------------------
    def run(self, plan: dict) -> dict:
        """
        Execute diagnostic steps defined in the plan.

        Returns:
            Dict[str, Any]: Structured diagnostic results
        """
        results = {}

        metric = plan["metric"]
        time_range = plan["time_range"]
        group_by = plan.get("group_by", [])
        filters = plan.get("filters", [])

        for step in plan.get("analysis_steps", []):
            if step == "compare_previous_period":
                results["period_comparison"] = self._compare_previous_period(
                    metric, time_range, group_by, filters
                )

            elif step == "rank_top_contributors":
                results["top_contributors"] = self._rank_top_contributors(
                    metric, time_range, group_by, filters
                )

            elif step.startswith("check_related_metric"):
                related_metric = step.split(":")[1]
                results[f"related_{related_metric}"] = self._check_related_metric(
                    related_metric, time_range, group_by, filters
                )

        return results

    # ---------------------------------------------------------
    # Diagnostic primitives
    # ---------------------------------------------------------
    def _compare_previous_period(
        self,
        metric: str,
        time_range: str,
        group_by: list,
        filters: list
    ) -> dict:
        """
        Compare metric between current and previous period.

        NOTE:
        v1 simplification:
        - current = last_month
        - previous = last_3_months (baseline proxy)
        """

        current_plan = {
            "intent": "descriptive",
            "metric": metric,
            "time_range": "last_month",
            "group_by": group_by,
            "filters": filters,
            "analysis_steps": []
        }

        previous_plan = {
            "intent": "descriptive",
            "metric": metric,
            "time_range": "last_3_months",
            "group_by": group_by,
            "filters": filters,
            "analysis_steps": []
        }

        current_sql = build_sql(current_plan, self.schema)
        previous_sql = build_sql(previous_plan, self.schema)

        current_df = self.sql_executor.execute(current_sql)
        previous_df = self.sql_executor.execute(previous_sql)

        return {
            "current_period": current_df,
            "previous_period": previous_df
        }

    def _rank_top_contributors(
        self,
        metric: str,
        time_range: str,
        group_by: list,
        filters: list
    ):
        """
        Rank contributors (dimensions) by metric value.
        """

        if not group_by:
            return {
                "warning": "No group_by dimensions provided; cannot rank contributors"
            }

        plan = {
            "intent": "descriptive",
            "metric": metric,
            "time_range": time_range,
            "group_by": group_by,
            "filters": filters,
            "analysis_steps": []
        }

        sql = build_sql(plan, self.schema)
        df = self.sql_executor.execute(sql)

        if metric not in df.columns:
            return {
                "warning": f"Metric {metric} not found in result"
            }

        return df.sort_values(by=metric, ascending=False)

    def _check_related_metric(
        self,
        related_metric: str,
        time_range: str,
        group_by: list,
        filters: list
    ):
        """
        Execute analysis for a related metric (e.g., avg_trip_distance).
        """

        plan = {
            "intent": "descriptive",
            "metric": related_metric,
            "time_range": time_range,
            "group_by": group_by,
            "filters": filters,
            "analysis_steps": []
        }

        sql = build_sql(plan, self.schema)
        return self.sql_executor.execute(sql)
