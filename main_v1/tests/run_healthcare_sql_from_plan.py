import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from schemas.healthcare_semantic_schema import HEALTHCARE_SCHEMA
from tools.sql_builder import build_sql
from tools.sql_executor import DuckDBExecutor


def _normalize_claims_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Map data1.csv-style columns to healthcare schema columns for SQL testing."""
    out = df.copy()

    alias_map = {
        "claim_id": "claimnumber",
        "year_month": "loadmonth",
        "selection_reason": "selectionreason",
        "CC_mcc_type": "drgconditiontype",
        "drg_code": "primarydiagnosiscode",
        "mdc_code": "mdcn",
        "savings_amount": "totalpaidamount",
        "provider": "providertaxid",
    }

    for target_col, source_col in alias_map.items():
        if target_col not in out.columns and source_col in out.columns:
            out[target_col] = out[source_col]

    if "finding_status" not in out.columns:
        if "exl_finding" in out.columns:
            out["finding_status"] = out["exl_finding"].apply(
                lambda v: "yes" if pd.notna(v) and float(v) > 0 else "no"
            )
        else:
            out["finding_status"] = "no"

    return out


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_sql_test(plan_path: Path, csv_path: Path, out_dir: Path) -> dict:
    with plan_path.open("r", encoding="utf-8") as f:
        plan = json.load(f)

    generated_sql = build_sql(plan, HEALTHCARE_SCHEMA)

    validation_sql = f"""
    SELECT COUNT(*) AS generated_row_count
    FROM (
      {generated_sql}
    ) AS generated_result
    """.strip()

    source_profile_sql = """
    SELECT
      COUNT(*) AS source_row_count,
      MIN(year_month) AS min_year_month,
      MAX(year_month) AS max_year_month
    FROM claims
    """.strip()

    _write_text(out_dir / "generated_query.sql", generated_sql)
    _write_text(out_dir / "validation_query.sql", validation_sql)
    _write_text(out_dir / "source_profile_query.sql", source_profile_sql)

    input_df = pd.read_csv(csv_path)
    normalized_df = _normalize_claims_dataframe(input_df)

    executor = DuckDBExecutor()
    try:
        executor.register_table("claims", normalized_df)

        generated_result = executor.execute(generated_sql)
        validation_result = executor.execute(validation_sql)
        source_profile_result = executor.execute(source_profile_sql)

        generated_result.to_csv(out_dir / "generated_query_output.csv", index=False)
        validation_result.to_csv(out_dir / "validation_query_output.csv", index=False)
        source_profile_result.to_csv(out_dir / "source_profile_output.csv", index=False)

        run_summary = {
            "plan_path": str(plan_path),
            "csv_path": str(csv_path),
            "out_dir": str(out_dir),
            "generated_sql_file": str(out_dir / "generated_query.sql"),
            "validation_sql_file": str(out_dir / "validation_query.sql"),
            "generated_result_file": str(out_dir / "generated_query_output.csv"),
            "validation_result_file": str(out_dir / "validation_query_output.csv"),
            "source_profile_result_file": str(out_dir / "source_profile_output.csv"),
            "generated_row_count": int(len(generated_result)),
        }

        _write_text(out_dir / "run_summary.json", json.dumps(run_summary, indent=2))
        return run_summary
    finally:
        executor.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate SQL from planner JSON and execute it on data1.csv"
    )
    parser.add_argument(
        "--plan-json",
        default="agent_example/tests/sample_plans/healthcare_plan_sample.json",
        help="Path to planner JSON file",
    )
    parser.add_argument(
        "--csv-path",
        default="agent_example/sample_data/data1.csv",
        help="Path to source CSV (data1.csv)",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory. If omitted, a timestamped folder under agent_example/test_outputs/sql_runs is used.",
    )

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path("agent_example/test_outputs/sql_runs") / timestamp

    try:
        summary = run_sql_test(
            plan_path=Path(args.plan_json),
            csv_path=Path(args.csv_path),
            out_dir=out_dir,
        )
        print("SQL generation and execution completed.")
        print(json.dumps(summary, indent=2))
    except Exception as exc:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_text(out_dir / "error.txt", f"{type(exc).__name__}: {exc}\n")
        raise


if __name__ == "__main__":
    main()
