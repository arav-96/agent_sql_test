# run_healthcare_plan_combinations - to validate scenarios end-to-end
import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from planners.planner_runner import normalize_plan
from planners.planner_validator import validate_plan
from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA
from tools.sql_builder import build_sql
from tools.sql_executor import DuckDBExecutor


def _normalize_claims_dataframe(df: pd.DataFrame) -> pd.DataFrame:
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

    if "approved" not in out.columns:
        out["approved"] = 0

    if "rejections" not in out.columns:
        out["rejections"] = out["approved"].apply(lambda v: 0 if str(v) == "1" else 1)

    return out


def _load_plans(plans_path: Path) -> list[dict]:
    payload = json.loads(plans_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "plans" in payload:
        return payload["plans"]
    if isinstance(payload, list):
        return payload
    raise ValueError("Input JSON must be either a list of plans or {'plans': [...]} format.")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_all(plans_path: Path, csv_path: Path, out_dir: Path, max_plans: int) -> dict:
    raw_plans = _load_plans(plans_path)[:max_plans]
    input_df = pd.read_csv(csv_path)
    normalized_df = _normalize_claims_dataframe(input_df)

    sql_dir = out_dir / "sql"
    out_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)

    all_sql_parts: list[str] = []
    rows = []

    executor = DuckDBExecutor()
    try:
        executor.register_table("claims", normalized_df)

        for index, raw_plan in enumerate(raw_plans, start=1):
            plan_id = f"plan_{index:03d}"
            normalized_plan = normalize_plan(raw_plan, HEALTHCARE_CLAIMS_SCHEMA)
            validation_errors = validate_plan(normalized_plan, HEALTHCARE_CLAIMS_SCHEMA)

            row = {
                "plan_id": plan_id,
                "status": "validated",
                "metric": normalized_plan.get("metric"),
                "time_range": normalized_plan.get("time_range"),
                "group_by": normalized_plan.get("group_by"),
                "validation_errors": validation_errors,
            }

            if validation_errors:
                row["status"] = "validation_failed"
                rows.append(row)
                continue

            if normalized_plan.get("metric") == "UNSUPPORTED_METRIC":
                row["status"] = "unsupported_metric"
                rows.append(row)
                continue

            try:
                sql = build_sql(normalized_plan, HEALTHCARE_CLAIMS_SCHEMA)
                sql_file = sql_dir / f"{plan_id}.sql"
                _write_text(sql_file, sql + "\n")

                all_sql_parts.append(f"-- {plan_id}\n{sql}\n")
                result_df = executor.execute(sql)
                result_file = out_dir / f"{plan_id}_result.csv"
                result_df.to_csv(result_file, index=False)

                row["status"] = "sql_generated"
                row["sql_file"] = str(sql_file)
                row["result_file"] = str(result_file)
                row["result_rows"] = int(len(result_df))
            except Exception as exc:
                row["status"] = "sql_error"
                row["error"] = f"{type(exc).__name__}: {exc}"

            rows.append(row)
    finally:
        executor.close()

    _write_text(out_dir / "all_generated_sql.sql", "\n".join(all_sql_parts))
    (out_dir / "run_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    summary = {
        "plans_processed": len(rows),
        "validated_and_sql_generated": sum(1 for r in rows if r["status"] == "sql_generated"),
        "validation_failed": sum(1 for r in rows if r["status"] == "validation_failed"),
        "unsupported_metric": sum(1 for r in rows if r["status"] == "unsupported_metric"),
        "sql_error": sum(1 for r in rows if r["status"] == "sql_error"),
        "plans_path": str(plans_path),
        "csv_path": str(csv_path),
        "output_dir": str(out_dir),
        "results_file": str(out_dir / "run_results.json"),
        "combined_sql_file": str(out_dir / "all_generated_sql.sql"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run up to 100 healthcare plan combinations through validator + SQL builder."
    )
    parser.add_argument(
        "--plans-json",
        default="tests/sample_plans/sql_builder_test_scenarios_100.json",
        help="Path to plans JSON.",
    )
    parser.add_argument(
        "--csv-path",
        default="test_data/data1.csv",
        help="Path to healthcare sample CSV.",
    )
    parser.add_argument(
        "--max-plans",
        type=int,
        default=100,
        help="Maximum plans to process.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Optional output directory. Defaults to timestamped folder under agent_example/test_outputs/plan_combinations.",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else Path("test_outputs/plan_combinations") / timestamp
    )

    summary = run_all(
        plans_path=Path(args.plans_json),
        csv_path=Path(args.csv_path),
        out_dir=out_dir,
        max_plans=max(1, args.max_plans),
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
