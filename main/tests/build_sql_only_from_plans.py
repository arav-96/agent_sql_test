# build_sql_only_from_plans.py - to test scenarios and sql_builder
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

import diagnostics.executor as diagnostic_module
from diagnostics.executor import DiagnosticExecutor
from planners.planner_runner import normalize_plan
from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA
from tools.sql_builder import build_sql
from tools.sql_executor import DuckDBExecutor


def _load_plans(plans_path: Path) -> list[dict]:
    payload = json.loads(plans_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "plans" in payload:
        plans = payload["plans"]
    elif isinstance(payload, list):
        plans = payload
    else:
        raise ValueError("Input JSON must be a list or {'plans': [...]} format")

    if not isinstance(plans, list):
        raise ValueError("'plans' must be a list")
    return plans


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def _classify_diagnostic_sql(sql: str) -> str:
    normalized = " ".join(sql.lower().split())
    if "group by year_month" in normalized:
        if "finding_status" in normalized:
            return "secondary_metric_baseline_hit_rate"
        if "sum(savings_amount)" in normalized:
            return "primary_metric_baseline"
        if "count(claim_id)" in normalized:
            return "secondary_metric_baseline_audit_volume"
        if "avg(savings_amount)" in normalized:
            return "secondary_metric_baseline_average_savings"
    if "select year_month" in normalized and "order by year_month desc" in normalized and "limit 1" in normalized:
        return "drilldown_current_month_lookup"
    if " as dim" in normalized and "group by selection_reason" in normalized:
        return "drilldown_dimension_selection_reason"
    if " as dim" in normalized and "group by cc_mcc_type" in normalized:
        return "drilldown_dimension_cc_mcc_type"
    if " as dim" in normalized and "group by drg_code" in normalized:
        return "drilldown_dimension_drg_code"
    if " as dim" in normalized and "group by mdc_code" in normalized:
        return "drilldown_dimension_mdc_code"
    return "diagnostic_sql"


class _TraceConnection:
    def __init__(self, inner, query_log: list[dict]):
        self._inner = inner
        self._query_log = query_log

    def execute(self, sql: str):
        self._query_log.append({"level": _classify_diagnostic_sql(sql), "sql": sql.strip()})
        return self._inner.execute(sql)

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _TraceDuckDBExecutor:
    def __init__(self):
        self._inner = DuckDBExecutor()
        self.query_log: list[dict] = []
        self._wrapped_connection = _TraceConnection(self._inner.get_connection(), self.query_log)

    def register_table(self, table_name: str, dataframe):
        return self._inner.register_table(table_name, dataframe)

    def get_connection(self):
        return self._wrapped_connection

    def execute(self, sql: str):
        self.query_log.append({"level": _classify_diagnostic_sql(sql), "sql": sql.strip()})
        return self._inner.execute(sql)

    def close(self):
        return self._inner.close()


def _diagnostic_plan_for_executor(plan: dict) -> dict:
    metric = plan.get("metric")
    mapped_metric = metric
    if metric in {"hitrate", "jhitrate"}:
        mapped_metric = "hit_rate"
    mapped = dict(plan)
    mapped["metric"] = mapped_metric
    return mapped


def build_sql_only(plans_path: Path, out_dir: Path, max_plans: int | None) -> dict:
    all_plans = _load_plans(plans_path)
    if max_plans is None or max_plans <= 0:
        plans = all_plans
    else:
        plans = all_plans[:max(1, max_plans)]
    out_dir.mkdir(parents=True, exist_ok=True)
    sql_dir = out_dir / "sql"
    sql_dir.mkdir(parents=True, exist_ok=True)

    combined_sql_parts: list[str] = []
    run_results: list[dict] = []

    for index, plan in enumerate(plans, start=1):
        plan_id = f"plan_{index:03d}"
        normalized_plan = normalize_plan(plan, HEALTHCARE_CLAIMS_SCHEMA)
        record = {
            "plan_id": plan_id,
            "plan": normalized_plan,
        }

        try:
            sql_entries: list[dict] = []

            if normalized_plan.get("intent") == "diagnostic":
                # Force expansion so diagnostic traces include secondary + drilldown SQL levels.
                diagnostic_module.PRIMARY_EXPANSION_THRESHOLD = 0.0
                csv_path = Path("sample_data/data1.csv")
                input_df = pd.read_csv(csv_path)
                normalized_df = _normalize_claims_dataframe(input_df)
                trace_executor = _TraceDuckDBExecutor()
                trace_executor.register_table("claims", normalized_df)
                try:
                    exec_plan = _diagnostic_plan_for_executor(normalized_plan)
                    DiagnosticExecutor(schema=HEALTHCARE_CLAIMS_SCHEMA, sql_executor=trace_executor).run(exec_plan)
                    sql_entries = trace_executor.query_log
                finally:
                    trace_executor.close()
            else:
                sql = build_sql(normalized_plan, HEALTHCARE_CLAIMS_SCHEMA)
                sql_entries = [{"level": "descriptive_main_sql", "sql": sql}]

            if not sql_entries:
                raise ValueError("No SQL generated for scenario")

            sql_bundle_text = "\n\n".join(
                [f"-- level: {entry['level']}\n{entry['sql']}" for entry in sql_entries]
            )
            sql_path = sql_dir / f"{plan_id}.sql"
            _write_text(sql_path, sql_bundle_text + "\n")

            combined_sql_parts.append(f"-- {plan_id}\n{sql_bundle_text}\n")
            record["status"] = "sql_generated"
            record["sql_file"] = str(sql_path)
            record["sql"] = sql_bundle_text
            record["sql_queries"] = sql_entries
        except Exception as exc:
            record["status"] = "sql_error"
            record["error"] = f"{type(exc).__name__}: {exc}"

        run_results.append(record)

    combined_sql_path = out_dir / "all_generated_sql.sql"
    _write_text(combined_sql_path, "\n".join(combined_sql_parts))

    results_path = out_dir / "run_results.json"
    _write_text(results_path, json.dumps(run_results, indent=2))

    combined_json_path = out_dir / "combined_plan_sql.json"
    _write_text(combined_json_path, json.dumps(run_results, indent=2))

    combined_csv_path = out_dir / "combined_plan_sql.csv"
    with combined_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "plan_id",
                "status",
                "intent",
                "metric",
                "time_range",
                "group_by",
                "filters",
                "analysis_steps",
                "sql",
                "error",
            ],
        )
        writer.writeheader()
        for r in run_results:
            plan = r.get("plan", {})
            writer.writerow(
                {
                    "plan_id": r.get("plan_id"),
                    "status": r.get("status"),
                    "intent": plan.get("intent"),
                    "metric": plan.get("metric"),
                    "time_range": plan.get("time_range"),
                    "group_by": json.dumps(plan.get("group_by", [])),
                    "filters": json.dumps(plan.get("filters", [])),
                    "analysis_steps": json.dumps(plan.get("analysis_steps", [])),
                    "sql": r.get("sql", ""),
                    "error": r.get("error", ""),
                }
            )

    requested_csv_path = out_dir / "scenario_results.csv"
    with requested_csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenario_number",
                "input_json",
                "test_case_status",
                "level",
                "sql_query_generated",
            ],
        )
        writer.writeheader()
        for r in run_results:
            scenario_number = r.get("plan_id", "").replace("plan_", "")
            input_json = json.dumps(
                r.get("plan", {}),
                separators=(",", ":"),
                ensure_ascii=False,
            )
            status = "passed" if r.get("status") == "sql_generated" else "failed"
            sql_queries = r.get("sql_queries", [])

            if sql_queries:
                for entry in sql_queries:
                    writer.writerow(
                        {
                            "scenario_number": scenario_number,
                            "input_json": input_json,
                            "test_case_status": status,
                            "level": entry.get("level", ""),
                            "sql_query_generated": entry.get("sql", ""),
                        }
                    )
            else:
                writer.writerow(
                    {
                        "scenario_number": scenario_number,
                        "input_json": input_json,
                        "test_case_status": status,
                        "level": "",
                        "sql_query_generated": "",
                    }
                )

    summary = {
        "plans_processed": len(run_results),
        "sql_generated": sum(1 for r in run_results if r["status"] == "sql_generated"),
        "sql_error": sum(1 for r in run_results if r["status"] == "sql_error"),
        "plans_path": str(plans_path),
        "output_dir": str(out_dir),
        "results_file": str(results_path),
        "combined_sql_file": str(combined_sql_path),
        "combined_json_file": str(combined_json_path),
        "combined_csv_file": str(combined_csv_path),
        "requested_results_csv_file": str(requested_csv_path),
    }

    _write_text(out_dir / "summary.json", json.dumps(summary, indent=2))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build SQL for each input plan without executing queries."
    )
    parser.add_argument(
        "--plans-json",
        default="tests/sample_plans/sql_builder_test_scenarios_100.json",
        help="Path to input plans JSON.",
    )
    parser.add_argument(
        "--max-plans",
        type=int,
        default=0,
        help="Maximum number of plans to process. Use 0 to run all scenarios.",
    )
    parser.add_argument(
        "--out-dir",
        default="",
        help="Optional output directory. Defaults to test_outputs/sql_only/<timestamp>.",
    )
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out_dir) if args.out_dir else Path("test_outputs/sql_only") / timestamp

    summary = build_sql_only(
        plans_path=Path(args.plans_json),
        out_dir=out_dir,
        max_plans=args.max_plans,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
