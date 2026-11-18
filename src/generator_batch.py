"""Batch telemetry producer: reads the IoT CSV, injects anomalies, POSTs batches.

Run from the project root:
    py -m src.generator_batch                      # 20,000 rows
    py -m src.generator_batch --rows 0             # all rows
    py -m src.generator_batch --batch-size 2000
"""
import argparse
import os
import random
import time
from pathlib import Path

import pandas as pd
import requests


API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/ingest/batch")
CSV_FILE = os.getenv("CSV_FILE", "data/iot_telemetry_data.csv")
BATCH_SIZE = 2000


def corrupt(p: dict) -> dict:
    """Inject one realistic defect into a payload."""
    kind = random.choice(["missing_field", "invalid_type", "out_of_bound"])
    if kind == "missing_field":
        p.pop("device_id", None)
    elif kind == "invalid_type":
        p["temp"] = "MALFORMED_TEMP"
    else:
        p["humidity"] = 150.0
    return p


def run(rows: int, anomaly_rate: float, batch_size: int, seed: int | None) -> None:
    if seed is not None:
        random.seed(seed)
    if not Path(CSV_FILE).exists():
        raise SystemExit(f"CSV not found: {CSV_FILE} (set CSV_FILE or move it into data/)")

    df = pd.read_csv(CSV_FILE, nrows=rows or None)
    records = [{
        "timestamp": float(r["ts"]),
        "device_id": str(r["device"]),
        "co": float(r["co"]),
        "humidity": float(r["humidity"]),
        "light": bool(r["light"]),
        "lpg": float(r["lpg"]),
        "motion": bool(r["motion"]),
        "smoke": float(r["smoke"]),
        "temp": float(r["temp"]),
    } for r in df.to_dict("records")]
    records = [corrupt(p) if random.random() < anomaly_rate else p for p in records]

    session = requests.Session()   # reuse the TCP connection across batches
    accepted = rejected = dupes = 0
    start = time.perf_counter()
    try:
        for i in range(0, len(records), batch_size):
            res = session.post(API_URL, json={"records": records[i:i + batch_size]}, timeout=60)
            res.raise_for_status()
            body = res.json()
            accepted += body["accepted"]
            rejected += body["rejected"]
            dupes += body["duplicates"]
    except requests.exceptions.ConnectionError:
        raise SystemExit("Cannot connect to the API. Is uvicorn running on port 8000?")
    elapsed = time.perf_counter() - start

    print(f"{len(records):,} rows in {elapsed:.1f}s ({len(records) / elapsed:,.0f} rows/s) "
          f"accepted={accepted:,} duplicates={dupes:,} rejected={rejected:,}")
    

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=20_000, help="0 = all rows")
    ap.add_argument("--anomaly-rate", type=float, default=0.05)
    ap.add_argument("--batch-size", type=int, default=500)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    run(a.rows, a.anomaly_rate, a.batch_size, a.seed)