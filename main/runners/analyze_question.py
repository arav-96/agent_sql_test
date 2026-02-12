from planners.planner_runner import run_planner
from planners.planner_validator import validate_plan
from diagnostics.executor import DiagnosticExecutor
from tools.sql_executor import DuckDBExecutor
from insights.schema import build_insight_payload
from insights.summarizer import summarize_insights
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA
from utils.logger import get_logger


logger = get_logger("analyze_question")


def analyze_question(question: str, duckdb_path: str) -> dict:
    """
    End-to-end orchestration:
    - Plan (LLM)
    - Validate
    - Apply system heuristics
    - Execute diagnostics
    - Build insight payload
    - Summarize results
    """

    # ----------------------------
    # Step 1: Planner
    # ----------------------------
    plan = run_planner(question)

    if plan.get("error"):
        return {"error": plan["error"], "details": plan}

    # ----------------------------
    # Step 2: Validation
    # ----------------------------
    errors = validate_plan(plan, TAXI_SEMANTIC_SCHEMA)
    if errors:
        return {
            "error": "INVALID_PLAN",
            "details": errors,
            "plan": plan
        }

    # -------------------------------------------------
    # Step 2.5: System heuristic (diagnostic fallback)
    # -------------------------------------------------
    if plan.get("intent") == "diagnostic" and not plan.get("group_by"):
        logger.info("Applying default diagnostic group_by: vendor")
        plan["group_by"] = ["vendor"]


    # -------------------------------------------------
    # System heuristic: default diagnostic steps
    # -------------------------------------------------
    if plan.get("intent") == "diagnostic" and not plan.get("analysis_steps"):
        logger.info(
            "Applying default diagnostic analysis steps: "
            "compare_previous_period, rank_top_contributors"
        )
        plan["analysis_steps"] = [
            "compare_previous_period",
            "rank_top_contributors"
        ]

    # ----------------------------
    # Step 3: Execute
    # ----------------------------
    executor = DuckDBExecutor(db_path=duckdb_path)

    if plan["intent"] == "descriptive":
        # Single descriptive query
        from tools.sql_builder import build_sql

        sql = build_sql(plan, TAXI_SEMANTIC_SCHEMA)
        result_df = executor.execute(sql)

        diagnostics = {
            "descriptive_result": result_df
        }

    else:
        # Diagnostic execution
        diagnostics = DiagnosticExecutor(
            schema=TAXI_SEMANTIC_SCHEMA,
            sql_executor=executor
        ).run(plan)


    # ----------------------------
    # Step 4: Build insight payload
    # ----------------------------
    payload = build_insight_payload(plan, diagnostics)

    # ----------------------------
    # Step 5: Summarize insights
    # ----------------------------
    summary = summarize_insights(payload)

    return {
        "plan": plan,
        "diagnostics": diagnostics,
        "summary": summary
    }
