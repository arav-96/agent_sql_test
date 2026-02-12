from tools.sql_executor import DuckDBExecutor
from tests.sample_data_claims import sample_claims_df


def test_duckdb_execution(sql_code: str):
    executor = DuckDBExecutor(":memory:")
    executor.register_table("df_final", sample_claims_df())

    # Example manual SQL if you want to test directly:
    # sql = """
    # SELECT VendorID, AVG(fare_amount) AS avg_fare
    # FROM taxi_analysis_ready
    # GROUP BY VendorID
    # """

    df = executor.execute(sql_code)
    print(df)

    assert not df.empty
