# claims_schema - modified to work for healthcare data
# Semantic schema for healthcare claims analytics

HEALTHCARE_CLAIMS_SCHEMA = {
    "table": "claims",
    "table_name": "claims",
    "raw_columns": [
        "claim_id","year_month","selection_reason","finding_status","CC_mcc_type","drg_code","mdc_code","savings_amount","provider","approved","rejections",
    ],
    "metrics": {
        "savings": {"column": "savings_amount", "aggregations": ["sum"], "description": "Total savings amount"},
        "audit_volume": {"column": "claim_id", "aggregations": ["count"], "description": "Audit volume"},
        "hit_rate": {"column": "finding_status", "aggregations": ["custom"], "expression": "SUM(CASE WHEN finding_status = 'yes' THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(claim_id), 0)", "description": "Hit rate"},
        "average_savings": {"column": "savings_amount", "aggregations": ["avg"], "description": "Average savings"},
        "claim_count": {"column": "*", "aggregations": ["count"], "description": "Claim count"},
        "total_paid_amount": {"column": "savings_amount", "aggregations": ["sum"], "description": "Total paid amount"},
        "avg_savings": {"column": "savings_amount", "aggregations": ["avg"], "description": "Average savings alias"},
        "avg_paidamount": {"column": "savings_amount", "aggregations": ["avg"], "description": "Average paid amount"},
        "hitrate": {"column": "finding_status", "aggregations": ["custom"], "expression": "SUM(CASE WHEN finding_status = 'yes' THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(claim_id), 0)", "description": "Hit rate alias"},
        "jhitrate": {"column": "finding_status", "aggregations": ["custom"], "expression": "SUM(CASE WHEN finding_status = 'yes' THEN 1 ELSE 0 END) * 1.0 / NULLIF(COUNT(claim_id), 0)", "description": "Provider health hit rate alias"},
        "audits": {"column": "claim_id", "aggregations": ["count"], "description": "Audits"},
        "selections": {"column": "approved", "aggregations": ["sum"], "description": "Selections"},
        "rejections": {"column": "rejections", "aggregations": ["sum"], "description": "Rejections"},
        "rejection_rate": {"column": "approved", "aggregations": ["custom"], "expression": "SUM(COALESCE(rejections, CASE WHEN approved = 0 THEN 1 ELSE 0 END)) * 1.0 / NULLIF(SUM(COALESCE(rejections, CASE WHEN approved = 0 THEN 1 ELSE 0 END)) + SUM(COALESCE(approved, 0)), 0)", "description": "Rejection rate"},
        "inscope_to_selection": {"column": "approved", "aggregations": ["custom"], "expression": "SUM(COALESCE(approved, 0)) * 1.0 / NULLIF(COUNT(*), 0)", "description": "Approved / total claims"},
        "inscope_to_selections": {"column": "approved", "aggregations": ["custom"], "expression": "SUM(COALESCE(approved, 0)) * 1.0 / NULLIF(COUNT(*), 0)", "description": "Alias for inscope_to_selection"},
    },
    "dimensions": {
        "selection_reason": {"column": "selection_reason"}, "CC_mcc_type": {"column": "CC_mcc_type"}, "drg_code": {"column": "drg_code"}, "mdc_code": {"column": "mdc_code"}, "provider": {"column": "provider"},
        "mode": {"column": "selection_reason"}, "audit_month": {"column": "year_month"}, "selection_month": {"column": "year_month"}, "mdcn_desc": {"column": "mdc_code"}, "drg_desc": {"column": "drg_code"},
        "provider_name": {"column": "provider"}, "cc_mcc_type": {"column": "CC_mcc_type"}, "drg_condition": {"column": "drg_code"}, "model_decile": {"column": "claim_id"}, "audit_type": {"column": "selection_reason"},
    },
    "time": {"column": "year_month", "supported_ranges": ["current_month","last_month","last_3_months","last_6_months","last_12_months","month_over_month"]},
}

HEALTHCARE_SCHEMA = HEALTHCARE_CLAIMS_SCHEMA
