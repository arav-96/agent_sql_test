import pandas as pd

def sample_taxi_df():
    return pd.DataFrame({
        "year_month": ["2024-12", "2024-12", "2025-01"],
        "VendorID": [1, 2, 1],
        "trip_distance": [2.5, 3.0, 4.0],
        "PULocationID": [100, 200, 100],
        "fare_amount": [10.0, 15.0, 20.0],
    })
