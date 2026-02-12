from tools.sql_builder import build_sql
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA


def test_avg_fare_last_month_by_vendor():
    plan = {
        "intent": "descriptive",
        "metric": "avg_fare",
        "time_range": "last_month",
        "group_by": ["vendor"],
        "filters": [],
        "analysis_steps": []
    }

    sql = build_sql(plan, TAXI_SEMANTIC_SCHEMA)
    print(sql)

    assert "AVG(fare_amount)" in sql
    assert "FROM taxi_analysis_ready" in sql
    assert "GROUP BY VendorID" in sql
