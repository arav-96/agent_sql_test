from tools.sql_builder import build_sql
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA


def test_simple_filters():
    plan = {
        "intent": "descriptive",
        "metric": "avg_fare",
        "time_range": "last_month",
        "group_by": ["vendor"],
        "filters": [
            {"field": "vendor", "op": "=", "value": 2},
            {"field": "trip_distance", "op": ">", "value": 5}
        ],
        "analysis_steps": []
    }

    sql = build_sql(plan, TAXI_SEMANTIC_SCHEMA)
    print(sql)

    assert "VendorID = 2" in sql
    assert "trip_distance > 5" in sql
