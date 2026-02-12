#"""Basic runner for SQL builder and executor tests."""

# %pip install pandas
# %pip install duckdb

from tests.test_sql_builder_claims import *
from tests.test_sql_executor_claims import test_duckdb_execution


def main() -> int:
    TEST_CASES = [
        {
            "test_id": 1,
            "test_name": "Total Claims by Category - Current Month",
            "plan": {
                "metric": "hitrate",
                "time_range": "month_over_month",
                "group_by": ["subprogram"],
                "filters": [],
                "comparison_type": None,
            },
        }
    ]

    print(f"\n✓ {len(TEST_CASES)} test case(s) defined")
    print("\nTest Case Details:")
    print(f"  ID: {TEST_CASES[0]['test_id']}")
    print(f"  Name: {TEST_CASES[0]['test_name']}")
    print(f"  Metric: {TEST_CASES[0]['plan']['metric']}")
    print(f"  Time Range: {TEST_CASES[0]['plan']['time_range']}")
    print(f"  Group By: {TEST_CASES[0]['plan']['group_by']}")

    print("\n" + "-" * 80)
    print("RUNNING TEST CASE...")
    print("-" * 80)

    plan = TEST_CASES[0]["plan"]

    # Capture SQL query from execute_healthcare_analysis
    sql_query = execute_healthcare_analysis(plan)

    tests = [
        ("execute_healthcare_analysis", lambda: execute_healthcare_analysis(plan)),
        ("test_duckdb_execution", lambda: test_duckdb_execution(sql_query)),
    ]

    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as exc:
            print(f"FAIL {name}: {exc}")
            failures += 1
        except Exception as exc:
            print(f"ERROR {name}: {exc}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
