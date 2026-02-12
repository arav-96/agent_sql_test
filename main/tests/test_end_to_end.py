from tools.sql_builder import build_sql
from tools.sql_executor import DuckDBExecutor
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA
from tests.sample_data import sample_taxi_df


def test_end_to_end_avg_fare():
    plan = {
        "intent": "descriptive",
        "metric": "avg_fare",
        "time_range": "last_month",
        "group_by": [],
        "filters": [],
        "analysis_steps": []
    }

    sql = build_sql(plan, TAXI_SEMANTIC_SCHEMA)

    executor = DuckDBExecutor()
    executor.register_table("taxi_analysis_ready", sample_taxi_df())

    df = executor.execute(sql)
    print(df)

    assert df.iloc[0]["avg_fare"] > 0
