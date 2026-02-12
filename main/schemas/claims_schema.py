# Semantic schema for Hum Prepay claims

HEALTHCARE_CLAIMS_SCHEMA = {
    # Physical table / dataframe
    "table": "df_final",

    # Metrics (aggregations)
    "metrics": {
        "claim_count": {
            "column": "*",
            "aggregations": ["count"],
            "description": "Total number of claims",
        },
        "total_paid_amount": {
            "column": "totalpaidamount",
            "aggregations": ["sum"],
            "description": "Total paid amount across all claims",
        },
        "hitrate": {
            "column": "exl_finding",
            "aggregations": ["custom"],
            "expression": (
                "SUM(exl_finding) / NULLIF(SUM(exl_finding) + SUM(exl_nofinding), 0)"
            ),
            "description": "Hit rate: sum(exl_finding) / (sum(exl_finding) + sum(exl_nofinding))",
        },
        "audits": {
            "column": "exl_finding",
            "aggregations": ["custom"],
            "expression": "SUM(exl_finding) + SUM(exl_nofinding)",
            "description": "Total audits: exl_finding + exl_nofinding",
        },
        "selections": {
            "column": "approved",
            "aggregations": ["sum"],
            "description": "Total selections: sum(approved)",
        },
    },

    # Dimensions (group‑by fields)
    "dimensions": {
        "category": {
            "column": "category",
            "description": "Claim category (CAT_AUTO_SEL, CAT_CVA_SEL, etc.)",
        },
        "drg_condition": {
            "column": "drgconditiontype",
            "description": "DRG condition type (MCC, CC, Other, etc.)",
        },
        "mdcn": {
            "column": "mdcn",
            "description": "Major Diagnostic Category Number",
        },
        "discharge_status": {
            "column": "dischargestatuscode",
            "description": "Discharge status code",
        },
        "subprogram": {
            "column": "subprogramtype",
            "description": "Subprogram type (CVA, DRG, etc.)",
        },
        "provider": {
            "column": "providertaxid",
            "description": "Provider tax ID (deidentified)",
        },
        "selection_month": {
            "column": "selection_month",
            "description": "Selection month (YYYYMM format)",
        },
    },

    # Time configuration
    "time": {
        "column": "loadmonth",
        "format": "YYYYMM",
        "supported_ranges": [
            "current_month",
            "last_month",
            "last_3_months",
            "last_6_months",
            "last_12_months",
            "month_over_month",
            "year_over_year",
        ],
    },

    # Comparison types
    "comparison_types": {
        "current_vs_historical": "Compare current month against historical average",
        "month_over_month": "Compare consecutive months",
        "trend_analysis": "Analyze trends over time periods",
    },
}

print("/ Healthcare Claims Semantic Schema created")
print(f"- {len(HEALTHCARE_CLAIMS_SCHEMA['metrics'])} metrics defined")
print(f"- {len(HEALTHCARE_CLAIMS_SCHEMA['dimensions'])} dimensions defined")
