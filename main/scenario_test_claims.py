import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from insights.schema import build_insight_payload
from planners.planner_validator_claims import validate_plan_claims
from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA
from tools.sql_builder_claims import build_claims_sql
from tools.sql_executor import DuckDBExecutor


def sample_scenarios() -> list[dict[str, Any]]:
    return [
        {
            "scenario_id": 1,
            "scenario_name": "Current month hitrate by subprogram",
            "question": "What is current month hitrate by subprogram?",
            "plan": {
                "intent": "descriptive",
                "metric": "hitrate",
                "time_range": "current_month",
                "group_by": ["subprogram"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 2,
            "scenario_name": "Last month total paid by category",
            "question": "Show last month total paid amount by category.",
            "plan": {
                "intent": "descriptive",
                "metric": "total_paid_amount",
                "time_range": "last_month",
                "group_by": ["category"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 3,
            "scenario_name": "Last 3 months claim count by DRG condition",
            "question": "How many claims in last 3 months by drg condition?",
            "plan": {
                "intent": "descriptive",
                "metric": "claim_count",
                "time_range": "last_3_months",
                "group_by": ["drg_condition"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 4,
            "scenario_name": "Last 6 months audits by subprogram",
            "question": "Total audits in last 6 months by subprogram.",
            "plan": {
                "intent": "descriptive",
                "metric": "audits",
                "time_range": "last_6_months",
                "group_by": ["subprogram"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 5,
            "scenario_name": "Selections for CVA only",
            "question": "Current month selections for subprogram CVA.",
            "plan": {
                "intent": "descriptive",
                "metric": "selections",
                "time_range": "current_month",
                "group_by": ["subprogram"],
                "filters": [{"column": "subprogramtype", "op": "=", "value": "CVA"}],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 6,
            "scenario_name": "Provider-level paid amount",
            "question": "Last month paid amount by provider tax id.",
            "plan": {
                "intent": "descriptive",
                "metric": "total_paid_amount",
                "time_range": "last_month",
                "group_by": ["provider"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 7,
            "scenario_name": "Category IN filter",
            "question": "Claim count for CAT_AUTO_SEL and CAT_CVA_SEL in last 12 months.",
            "plan": {
                "intent": "descriptive",
                "metric": "claim_count",
                "time_range": "last_12_months",
                "group_by": ["category"],
                "filters": [
                    {
                        "column": "category",
                        "op": "IN",
                        "value": ["CAT_AUTO_SEL", "CAT_CVA_SEL"],
                    }
                ],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 8,
            "scenario_name": "Month over month hitrate trend",
            "question": "Hitrate month over month by selection month.",
            "plan": {
                "intent": "descriptive",
                "metric": "hitrate",
                "time_range": "month_over_month",
                "group_by": ["selection_month"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 9,
            "scenario_name": "Year over year claim count",
            "question": "Claim count year over year by subprogram.",
            "plan": {
                "intent": "descriptive",
                "metric": "claim_count",
                "time_range": "year_over_year",
                "group_by": ["subprogram"],
                "filters": [],
                "analysis_steps": [],
            },
        },
        {
            "scenario_id": 10,
            "scenario_name": "Diagnostic-style plan with related metric step",
            "question": "Why did hitrate change last month by category?",
            "plan": {
                "intent": "diagnostic",
                "metric": "hitrate",
                "time_range": "last_month",
                "group_by": ["category"],
                "filters": [],
                "analysis_steps": [
                    "compare_previous_period",
                    "rank_top_contributors",
                    "check_related_metric:total_paid_amount",
                ],
            },
        },
    ]


def load_scenarios_from_csv(path: str) -> list[dict[str, Any]]:
    """
    Expected columns:
    - scenario_id
    - scenario_name
    - question
    - plan_json (stringified JSON object)
    """
    df = pd.read_csv(path)
    required = {"scenario_id", "scenario_name", "question", "plan_json"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required scenario columns: {missing}")

    scenarios: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        scenarios.append(
            {
                "scenario_id": int(row["scenario_id"]),
                "scenario_name": str(row["scenario_name"]),
                "question": str(row["question"]),
                "plan": json.loads(row["plan_json"]),
            }
        )
    return scenarios


def _to_json_str(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def run_scenarios(
    claims_csv: str,
    output_csv: str,
    scenarios_csv: str | None = None,
    max_output_rows: int = 25,
) -> None:
    claims_df = pd.read_csv(claims_csv)

    executor = DuckDBExecutor(":memory:")
    executor.register_table(HEALTHCARE_CLAIMS_SCHEMA["table"], claims_df)

    scenarios = (
        load_scenarios_from_csv(scenarios_csv)
        if scenarios_csv
        else sample_scenarios()
    )

    rows: list[dict[str, Any]] = []
    for s in scenarios:
        scenario_id = s["scenario_id"]
        scenario_name = s["scenario_name"]
        question = s["question"]
        plan = s["plan"]

        errors = validate_plan_claims(plan, HEALTHCARE_CLAIMS_SCHEMA)
        is_valid = len(errors) == 0

        sql_query = ""
        sql_result_preview: list[dict[str, Any]] = []
        sql_result_row_count = 0
        summarizer_payload: dict[str, Any] = {}
        execution_status = "SKIPPED"
        execution_error = ""

        if is_valid and plan.get("metric") != "UNSUPPORTED_METRIC":
            try:
                sql_query = build_claims_sql(plan, HEALTHCARE_CLAIMS_SCHEMA)
                result_df = executor.execute(sql_query)
                sql_result_row_count = int(len(result_df))
                sql_result_preview = result_df.head(max_output_rows).to_dict(
                    orient="records"
                )

                diagnostics = {"descriptive_result": result_df}
                summarizer_payload = build_insight_payload(plan, diagnostics)
                execution_status = "OK"
            except Exception as exc:
                execution_status = "ERROR"
                execution_error = str(exc)

        rows.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "question": question,
                "plan_json": _to_json_str(plan),
                "validator_status": "PASS" if is_valid else "FAIL",
                "validator_errors_json": _to_json_str(errors),
                "sql_layer_input_json": _to_json_str(
                    {
                        "table": HEALTHCARE_CLAIMS_SCHEMA["table"],
                        "plan": plan,
                    }
                ),
                "generated_sql": sql_query,
                "sql_output_row_count": sql_result_row_count,
                "sql_output_preview_json": _to_json_str(sql_result_preview),
                "summarizer_input_payload_json": _to_json_str(summarizer_payload),
                "execution_status": execution_status,
                "execution_error": execution_error,
            }
        )

    executor.close()

    output_df = pd.DataFrame(rows)
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_csv, index=False)
    print(f"Wrote {len(output_df)} scenario rows to {output_csv}")


def main() -> int:
    base_dir = Path(__file__).resolve().parent
    default_claims_csv = str(base_dir / "test_data" / "data1.csv")
    default_output_csv = str(base_dir / "test_data" / "claims_scenario_output.csv")

    parser = argparse.ArgumentParser(
        description=(
            "Run 10 claims scenarios through validator + SQL builder/executor and "
            "store summarizer input payload per scenario."
        )
    )
    parser.add_argument(
        "--claims-csv",
        type=str,
        default=default_claims_csv,
        help="Path to claims input CSV used as SQL data layer.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default=default_output_csv,
        help="Path to output CSV report.",
    )
    parser.add_argument(
        "--scenarios-csv",
        type=str,
        default=None,
        help=(
            "Optional scenario input CSV with columns: scenario_id, scenario_name, "
            "question, plan_json. If omitted, built-in 10 sample scenarios are used."
        ),
    )
    parser.add_argument(
        "--max-output-rows",
        type=int,
        default=25,
        help="Max number of SQL result rows stored in sql_output_preview_json.",
    )
    args = parser.parse_args()

    run_scenarios(
        claims_csv=args.claims_csv,
        output_csv=args.output_csv,
        scenarios_csv=args.scenarios_csv,
        max_output_rows=args.max_output_rows,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
