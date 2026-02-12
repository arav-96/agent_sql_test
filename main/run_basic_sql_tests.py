"""Basic runner for SQL builder and executor tests."""

from tests.test_sql_builder import test_avg_fare_last_month_by_vendor
from tests.test_sql_executor import test_duckdb_execution


def main() -> int:
    tests = [
        ("test_avg_fare_last_month_by_vendor", test_avg_fare_last_month_by_vendor),
        ("test_duckdb_execution", test_duckdb_execution),
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
