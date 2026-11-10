import os
import time
import random
import pandas as pd
import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/ingest")
CSV_FILE = "iot_telemetry_data.csv"

def generate_telemetry_stream(anomaly_rate: float = 0.05, delay: float = 0.1):
    """
    Reads rows from the IoT telemetry CSV, optionally injects anomalies,
    and dispatches them via HTTP POST to the ingestion service.
    """
    if not os.path.exists(CSV_FILE):
        print(f"Error: {CSV_FILE} not found in working directory.")
        return

    df = pd.read_csv(CSV_FILE)
    print(f"Loaded {len(df):,} rows from {CSV_FILE}. Starting simulation stream...")

    for index, row in df.iterrows():
        # Construct standard telemetry payload from CSV row
        payload = {
            "timestamp": float(row["ts"]),
            "device_id": str(row["device"]),
            "co": float(row["co"]),
            "humidity": float(row["humidity"]),
            "light": bool(row["light"]),
            "lpg": float(row["lpg"]),
            "motion": bool(row["motion"]),
            "smoke": float(row["smoke"]),
            "temp": float(row["temp"])
        }

        # Intentionally inject bad data to test Pydantic validation boundaries
        if random.random() < anomaly_rate:
            anomaly_type = random.choice(["missing_field", "invalid_type", "out_of_bound"])
            if anomaly_type == "missing_field":
                payload.pop("device_id", None)
            elif anomaly_type == "invalid_type":
                payload["temp"] = "MALFORMED_TEMP"  # String instead of float
            elif anomaly_type == "out_of_bound":
                payload["humidity"] = 150.0       # Exceeds max limit of 100%

        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code == 200:
                print(f"[SUCCESS] Row {index}: Ingested data for device {payload.get('device_id', 'UNKNOWN')}")
            else:
                print(f"[REJECTED/VALIDATION ERROR] Row {index}: Status {response.status_code} - {response.text}")
        except requests.exceptions.ConnectionError:
            print("[ERROR] Cannot connect to FastAPI backend. Make sure uvicorn is running on port 8000.")
            break

        time.sleep(delay)

if __name__ == "__main__":
    # Run simulation with a 5% anomaly rate and 0.1 second delay between events
    generate_telemetry_stream(anomaly_rate=0.05, delay=0.1)