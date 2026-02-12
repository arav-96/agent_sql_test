import pandas as pd


def build_insight_payload(plan: dict, diagnostics: dict) -> dict:
    payload = {
        "intent": plan["intent"],
        "metric": plan["metric"],
        "time_range": plan["time_range"],
        "findings": {}
    }

    # Existing diagnostic handling (unchanged)
    if "period_comparison" in diagnostics:
        period = diagnostics["period_comparison"]
        payload["findings"]["period_comparison"] = {
            "current_value": period["current_period"].to_dict(orient="records"),
            "previous_value": period["previous_period"].to_dict(orient="records")
        }

    if "top_contributors" in diagnostics:
        top = diagnostics["top_contributors"]
        if isinstance(top, pd.DataFrame):
            payload["findings"]["top_contributors"] = top.head(5).to_dict(orient="records")
        else:
            payload["findings"]["top_contributors"] = top

    for key, value in diagnostics.items():
        if key.startswith("related_"):
            if isinstance(value, pd.DataFrame):
                payload["findings"][key] = value.to_dict(orient="records")
            else:
                payload["findings"][key] = value

    # ----------------------------
    # NEW: Descriptive result
    # ----------------------------
    if "descriptive_result" in diagnostics:
        payload["findings"]["descriptive_result"] = diagnostics[
            "descriptive_result"
        ].to_dict(orient="records")

    return payload
