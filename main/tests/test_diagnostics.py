from diagnostics.executor import DiagnosticExecutor
from tools.sql_executor import DuckDBExecutor
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA
from tests.sample_data import sample_taxi_df


def test_diagnostic_execution():
    executor = DuckDBExecutor()
    executor.register_table("taxi_analysis_ready", sample_taxi_df())

    diag = DiagnosticExecutor(
        schema=TAXI_SEMANTIC_SCHEMA,
        sql_executor=executor
    )

    plan = {
        "intent": "diagnostic",
        "metric": "avg_fare",
        "time_range": "last_month",
        "group_by": ["vendor"],
        "filters": [],
        "analysis_steps": [
            "compare_previous_period",
            "rank_top_contributors"
        ]
    }

    results = diag.run(plan)
    print(results)

    assert "period_comparison" in results
    assert "top_contributors" in results
