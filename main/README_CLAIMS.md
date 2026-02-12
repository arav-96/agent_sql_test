# Claims Track Overview

This document describes the **claims track** in this project: what each file does, and the expected input/output formats.

## End-to-End (Claims) Flow

1. User question (text) is converted to a structured plan by the claims planner.
2. Plan is validated against the claims semantic schema.
3. SQL is built from the plan and executed on DuckDB (or test in-memory table).
4. Query/diagnostic results are converted to a payload dictionary.
5. Payload is summarized into plain language.

---

## Core Claims Files

- `main/schemas/claims_schema.py`
  - Defines claims semantic schema:
    - physical table name
    - allowed metrics
    - allowed dimensions
    - time column and supported ranges

- `main/prompts/planner_prompt_claims.py`
  - Builds planner prompt messages for claims questions.
  - Function:
    - `build_planner_prompt_claims(user_question: str) -> list`

- `main/planners/planner_runner_claims.py`
  - Calls Azure OpenAI to generate claims plan JSON.
  - Function:
    - `run_planner_claims(user_question: str) -> dict`

- `main/planners/planner_validator_claims.py`
  - Validates claims plan shape and allowed values.
  - Function:
    - `validate_plan_claims(plan: dict, schema: dict) -> list[str]`

- `main/tools/sql_builder_claims.py`
  - Converts validated claims plan to SQL.
  - Function:
    - `build_claims_sql(plan: dict, schema: dict) -> str`

- `main/tools/sql_executor.py`
  - Executes SQL in DuckDB.
  - Class:
    - `DuckDBExecutor(db_path: str)`
    - `execute(sql: str) -> pandas.DataFrame`
    - `register_table(name: str, df: DataFrame) -> None`

- `main/insights/schema.py`
  - Converts result DataFrames into serializable payload dict.
  - Function:
    - `build_insight_payload(plan: dict, diagnostics: dict) -> dict`

- `main/insights/summarizer_claims.py`
  - Calls Azure OpenAI to produce final text summary for claims payload.
  - Function:
    - `summarize_insights_claims(payload: dict) -> str`

- `main/tests/test_sql_builder_claims.py`
  - Helper/testing function to run claims SQL generation.
  - Function:
    - `execute_healthcare_analysis(plan: dict, df: object | None = None) -> object`
    - Current return is SQL string.

- `main/tests/test_sql_executor_claims.py`
  - Executes generated claims SQL against in-memory DuckDB.
  - Function:
    - `test_duckdb_execution(sql_code: str) -> None`

- `main/run_basic_sql_tests_claims.py`
  - Basic runner for claims SQL builder + executor tests.

---

## Input / Output Formats

## 1) Planner Input

- Function: `run_planner_claims(user_question: str) -> dict`
- Input:
  - `user_question`: plain natural-language string

Example:
```text
"Why did hitrate change last month by subprogram?"
```

## 2) Planner Output (Plan JSON)

Expected keys:
```json
{
  "intent": "descriptive | diagnostic",
  "metric": "string",
  "time_range": "string",
  "group_by": ["dimension_key"],
  "filters": [
    {
      "column": "physical_column_name",
      "op": "= | != | > | >= | < | <= | LIKE | IN",
      "value": "string | number | list"
    }
  ],
  "analysis_steps": ["step_name"]
}
```

Notes:
- `metric` must exist in `HEALTHCARE_CLAIMS_SCHEMA["metrics"]` or be `"UNSUPPORTED_METRIC"`.
- `group_by` values must be schema dimension keys (e.g. `subprogram`, `category`).
- `time_range` must be in claims schema supported ranges.

## 3) Validator Output

- Function: `validate_plan_claims(plan, schema) -> list[str]`
- Output:
  - `[]` means valid
  - non-empty list contains validation errors

## 4) SQL Builder Input / Output

- Function: `build_claims_sql(plan, schema) -> str`
- Input:
  - validated plan dict
  - claims schema dict
- Output:
  - SQL query string

## 5) SQL Executor Input / Output

- Function: `DuckDBExecutor.execute(sql) -> pandas.DataFrame`
- Input:
  - SQL string
- Output:
  - DataFrame with result rows/columns

## 6) Insight Payload Format

- Function: `build_insight_payload(plan, diagnostics) -> dict`
- Output shape:
```json
{
  "intent": "descriptive | diagnostic",
  "metric": "metric_name",
  "time_range": "time_range_name",
  "findings": {
    "descriptive_result": [{ "...": "..." }],
    "period_comparison": {
      "current_value": [{ "...": "..." }],
      "previous_value": [{ "...": "..." }]
    },
    "top_contributors": [{ "...": "..." }],
    "related_<metric>": [{ "...": "..." }]
  }
}
```

Keys inside `findings` are optional and depend on which analysis steps ran.

## 7) Summarizer Input / Output

- Function: `summarize_insights_claims(payload: dict) -> str`
- Input:
  - payload dict in the format above
- Output:
  - plain-language summary string

---

## Minimal Claims Data Requirements

Claims CSV/table columns should match schema mappings in `main/schemas/claims_schema.py`, including:

- `totalpaidamount`
- `loadmonth`
- `category`
- `subprogramtype`
- `providertaxid`
- `exl_finding`
- `exl_nofinding`
- `drgconditiontype`
- `mdcn`
- `selection_month`

The claims schema table name is currently `df_final`, so registered/executed data should be available with that name.
