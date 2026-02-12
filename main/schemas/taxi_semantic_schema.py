TAXI_SEMANTIC_SCHEMA = {
    # ----------------------------
    # Physical table
    # ----------------------------
    "table": "taxi_analysis_ready",

    # ----------------------------
    # Metrics (aggregations)
    # ----------------------------
    "metrics": {
        "avg_fare": {
            "column": "fare_amount",
            "aggregations": ["avg"]
        },
        "total_fare": {
            "column": "fare_amount",
            "aggregations": ["sum"]
        },
        "avg_trip_distance": {
            "column": "trip_distance",
            "aggregations": ["avg"]
        },
        "trip_count": {
            "column": "*",
            "aggregations": ["count"]
        }
    },

    # ----------------------------
    # Dimensions (group-by fields)
    # ----------------------------
    "dimensions": {
        "vendor": {
            "column": "VendorID"
        },
        "pickup_location": {
            "column": "PULocationID"
        }
    },

    # ----------------------------
    # Time configuration
    # ----------------------------
    "time": {
        "column": "year_month",
        "supported_ranges": {
            "last_month",
            "last_3_months"
        }
    },

    # ----------------------------
    # Raw columns allowed in filters
    # ----------------------------
    "raw_columns": {
        "trip_distance",
        "fare_amount",
        "VendorID",
        "PULocationID"
    }
}
