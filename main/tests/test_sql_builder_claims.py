from tools.sql_builder_claims import build_claims_sql
from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA
from tests.sample_data_claims import sample_claims_df


def execute_healthcare_analysis(plan: dict, df: object = None) -> object:
    """
    Execute healthcare claims analysis plan.

    Parameters
    ----------
    plan : dict
        Analysis plan with metric, time_range, group_by, filters, comparison_type.
    df : DataFrame, optional
        DataFrame to analyze (defaults to df_final).

    Returns
    -------
    object
        Query result (currently the generated SQL string or DataFrame in future).
    """
    if df is None:
        df = sample_claims_df()

    # Create temp view for SQL execution (if you later integrate with Spark/DuckDB)
    # e.g., register df as "df_final" in your executor

    # Build SQL
    sql = build_claims_sql(plan, HEALTHCARE_CLAIMS_SCHEMA)

    print("=== Generated SQL ===")
    print(sql)
    print("=== Executing Query ===")
    # When wired to an engine:
    # result = spark.sql(sql) or executor.execute(sql)
    # return result

    return sql


print("/ execute_healthcare_analysis function created")
print("\n" + "=" * 60)
print("Healthcare Claims Analysis Framework Ready!")
print("=" * 60)
