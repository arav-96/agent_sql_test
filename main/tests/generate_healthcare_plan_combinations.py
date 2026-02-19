# generate_healthcare_plan_combinations - scenarios to test
import argparse
import json
from itertools import product
from pathlib import Path

from schemas.claims_schema import HEALTHCARE_CLAIMS_SCHEMA


def _schema_metric_keys(schema: dict) -> list[str]:
    metrics = schema.get("metrics", {})
    if isinstance(metrics, dict):
        return list(metrics.keys())
    if isinstance(metrics, (list, set, tuple)):
        return list(metrics)
    return []


def _schema_dimension_keys(schema: dict) -> list[str]:
    dimensions = schema.get("dimensions", {})
    if isinstance(dimensions, dict):
        return list(dimensions.keys())
    if isinstance(dimensions, (list, set, tuple)):
        return list(dimensions)
    return []


def _filter_options(dimension_keys: list[str]) -> list[list[dict]]:
    preferred_dim_filters = [d for d in ["mode", "provider_name", "audit_type"] if d in dimension_keys]
    dim_field = preferred_dim_filters[0] if preferred_dim_filters else (dimension_keys[0] if dimension_keys else "mode")

    return [
        [],
        [{"field": "approved", "op": "=", "value": 1}],
        [{"field": "approved", "op": "=", "value": 0}],
        [{"field": "approved", "op": "!=", "value": 0}],
        [{"field": "approved", "op": "=", "value": None}],
        [{"field": "approved", "op": "!=", "value": None}],
        [{"field": dim_field, "op": "=", "value": "MSDRG"}],
        [{"field": dim_field, "op": "!=", "value": "DRGCL"}],
        [{"field": "claim_id", "op": ">", "value": 1000}],
        [{"field": "claim_id", "op": ">=", "value": 1}],
        [{"field": "claim_id", "op": "<", "value": 5000000}],
        [{"field": "claim_id", "op": "<=", "value": 9999999}],
        [
            {"field": "approved", "op": "=", "value": 1},
            {"field": dim_field, "op": "!=", "value": "whole"},
        ],
    ]


def _build_group_options(dim_order: list[str]) -> list[list[str]]:
    single_dim = [[d] for d in dim_order[:8]]
    two_dim = []
    for i in range(min(5, len(dim_order))):
        for j in range(i + 1, min(8, len(dim_order))):
            two_dim.append([dim_order[i], dim_order[j]])
    return [[]] + single_dim + two_dim[:6]


def _default_intent(metric: str) -> str:
    diagnostic_metrics = {"savings", "audit_volume", "hitrate", "hit_rate", "jhitrate"}
    return "diagnostic" if metric in diagnostic_metrics else "descriptive"


def _analysis_steps(metric: str, intent: str, group_by: list[str], metric_order: list[str]) -> list[str]:
    if intent != "diagnostic":
        return []

    steps = ["compare_previous_period"]
    if metric == "jhitrate":
        steps.append("provider_health_scan")
    if metric in {"savings", "audit_volume", "hitrate", "hit_rate"}:
        steps.append("rank_top_decliners")
        steps.append("rank_top_contributors")

    secondary = next((m for m in metric_order if m != metric), None)
    if secondary:
        steps.append(f"check_secondary_metric:{secondary}")
    if group_by:
        steps.append(f"drill_by_dimension:{group_by[0]}")
    return steps


def _plan_signature(plan: dict) -> str:
    return json.dumps(plan, sort_keys=True, separators=(",", ":"))


def build_plan_combinations(schema: dict, limit: int = 100) -> list[dict]:
    metric_keys = _schema_metric_keys(schema)
    dimension_keys = _schema_dimension_keys(schema)
    time_ranges = list(schema.get("time", {}).get("supported_ranges", []))

    if not metric_keys or not time_ranges:
        return []

    preferred_metrics = [
        "savings",
        "audit_volume",
        "hit_rate",
        "hitrate",
        "jhitrate",
        "avg_savings",
        "selections",
        "rejection_rate",
        "inscope_to_selection",
        "avg_paidamount",
        "claim_count",
    ]
    metric_order = [m for m in preferred_metrics if m in metric_keys]
    metric_order.extend([m for m in metric_keys if m not in metric_order])

    preferred_dims = [
        "mode",
        "provider_name",
        "audit_month",
        "selection_month",
        "mdcn_desc",
        "drg_desc",
        "audit_type",
        "cc_mcc_type",
        "drg_condition",
        "model_decile",
        "selection_reason",
        "provider",
    ]
    dim_order = [d for d in preferred_dims if d in dimension_keys]
    dim_order.extend([d for d in dimension_keys if d not in dim_order])

    group_by_options = _build_group_options(dim_order)
    filter_options = _filter_options(dim_order)

    candidates = []
    for time_range, metric, group_by, filters in product(
        time_ranges, metric_order, group_by_options, filter_options
    ):
        default_intent = _default_intent(metric)
        intents = [default_intent]
        if default_intent == "descriptive":
            intents.append("diagnostic")

        for intent in intents:
            candidates.append(
                {
                    "intent": intent,
                    "metric": metric,
                    "time_range": time_range,
                    "group_by": group_by,
                    "filters": filters,
                    "analysis_steps": _analysis_steps(metric, intent, group_by, metric_order),
                }
            )

    seen = set()
    plans = []

    # Balanced round-robin selection to maximize diversity in first N plans.
    buckets = {
        "diagnostic": [p for p in candidates if p["intent"] == "diagnostic"],
        "descriptive": [p for p in candidates if p["intent"] == "descriptive"],
    }
    indices = {"diagnostic": 0, "descriptive": 0}

    while len(plans) < limit:
        progressed = False
        for intent in ["diagnostic", "descriptive"]:
            idx = indices[intent]
            if idx >= len(buckets[intent]):
                continue
            plan = buckets[intent][idx]
            indices[intent] += 1
            sig = _plan_signature(plan)
            if sig in seen:
                continue
            seen.add(sig)
            plans.append(plan)
            progressed = True
            if len(plans) >= limit:
                break
        if not progressed:
            break

    return plans


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate sample healthcare planner JSON combinations."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of plans to generate.",
    )
    parser.add_argument(
        "--out-json",
        default="tests/sample_plans/sql_builder_test_scenarios_100.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    plans = build_plan_combinations(HEALTHCARE_CLAIMS_SCHEMA, limit=max(1, args.limit))
    output = {"plans": plans}

    out_path = Path(args.out_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Generated {len(plans)} plans at: {out_path}")


if __name__ == "__main__":
    main()
