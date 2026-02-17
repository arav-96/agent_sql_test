from planners.planner_runner import run_planner
from planners.planner_validator import validate_plan
from schemas.healthcare_semantic_schema import HEALTHCARE_SCHEMA
from utils.logger import get_logger

logger = get_logger("planner_test")


def run_and_validate(question: str):
    plan = run_planner(question, schema=HEALTHCARE_SCHEMA)

    # ----------------------------
    # 1. No response / hard failure
    # ----------------------------
    if plan is None:
        logger.error("NO RESPONSE FROM PLANNER")
        logger.error(f"Question: {question}")
        return

    # ----------------------------
    # 2. Planner returned structured error
    # ----------------------------
    if plan.get("error"):
        logger.warning("PLANNER RETURNED ERROR")
        logger.warning(f"Question: {question}")
        logger.warning(f"Plan/Error: {plan}")
        return

    # ----------------------------
    # 3. Validate planner output
    # ----------------------------
    errors = validate_plan(plan, HEALTHCARE_SCHEMA)

    metric = plan.get("metric", "")

    # ----------------------------
    # 4. Logging semantics
    # ----------------------------
    if errors:
        logger.error("VALIDATION FAILED")
        logger.error(f"Question: {question}")
        logger.error(f"Plan: {plan}")
        for e in errors:
            logger.error(f"Reason: {e}")

    elif metric == "UNSUPPORTED_METRIC":
        logger.warning("VALIDATION PASSED WITH UNSUPPORTED METRIC")
        logger.warning(f"Question: {question}")
        logger.warning(f"Plan: {plan}")

    else:
        logger.info("VALIDATION PASSED")
        logger.info(f"Question: {question}")
        logger.info(f"Plan: {plan}")


if __name__ == "__main__":
    test_questions = [
        "What is the savings in the last month?",
        "Why did audit volume drop in the last 3 months?",
        "Show hit rate trend for the last 3 months by provider_name.",
    ]

    for q in test_questions:
        run_and_validate(q)
