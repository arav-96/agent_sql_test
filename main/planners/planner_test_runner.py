from planners.planner_runner import run_planner
from planners.planner_validator import validate_plan
from schemas.taxi_semantic_schema import TAXI_SEMANTIC_SCHEMA
from utils.logger import get_logger

logger = get_logger("planner_test")


def run_and_validate(question: str):
    plan = run_planner(question)

    # ----------------------------
    # 1. No response / hard failure
    # ----------------------------
    if plan is None:
        logger.error("NO RESPONSE FROM PLANNER")
        logger.error(f"Question: {question}")
        return

    # ----------------------------
    # 2. Azure content filter
    # ----------------------------
    if plan.get("error") == "CONTENT_FILTERED":
        logger.warning("PLANNER BLOCKED BY AZURE CONTENT FILTER")
        logger.warning(f"Question: {question}")
        return

    # ----------------------------
    # 3. Validate planner output
    # ----------------------------
    errors = validate_plan(plan, TAXI_SEMANTIC_SCHEMA)

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
