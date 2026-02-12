from tools.sql_executor import DuckDBExecutor
from tests.sample_data import sample_taxi_df


def test_duckdb_execution():
    executor = DuckDBExecutor(":memory:")
    executor.register_table("taxi_analysis_ready", sample_taxi_df())

    sql = """
    SELECT VendorID, AVG(fare_amount) AS avg_fare
    FROM taxi_analysis_ready
    GROUP BY VendorID
    """

    df = executor.execute(sql)
    print(df)

    assert not df.empty
