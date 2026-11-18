MAC = "b8:27:eb:bf:9d:51"


def good(ts: float = 1594512094.38, **overrides) -> dict:
    rec = {
        "timestamp": ts, "device_id": MAC, "co": 0.0049, "humidity": 51.0,
        "light": False, "lpg": 0.0076, "motion": False, "smoke": 0.0204, "temp": 22.7,
    }
    rec.update(overrides)
    return rec


def metrics(client) -> dict:
    return client.get("/metrics").json()


# ---------- health / empty state ----------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "healthy"


def test_metrics_empty_database(client):
    m = metrics(client)
    assert m["totals"] == {"received": 0, "stored": 0, "rejected": 0}
    assert m["error_rate_pct"] == 0.0
    assert m["unique_devices"] == 0


# ---------- single-record endpoint ----------
def test_ingest_valid_record(client):
    r = client.post("/ingest", json=good())
    assert r.status_code == 200
    assert r.json()["status"] == "success" and r.json()["record_id"] is not None


def test_ingest_duplicate_returns_409(client):
    assert client.post("/ingest", json=good()).status_code == 200
    assert client.post("/ingest", json=good()).status_code == 409


def test_ingest_invalid_is_422_and_quarantined(client):
    bad = good()
    bad.pop("device_id")
    assert client.post("/ingest", json=bad).status_code == 422
    m = metrics(client)
    assert m["totals"]["rejected"] == 1 and m["totals"]["stored"] == 0


def test_ingest_rejects_out_of_range_and_wrong_type(client):
    assert client.post("/ingest", json=good(humidity=150.0)).status_code == 422
    assert client.post("/ingest", json=good(temp="MALFORMED_TEMP")).status_code == 422
    assert client.post("/ingest", json=good(smoke=-1.0)).status_code == 422


def test_device_id_pattern_and_normalisation(client):
    assert client.post("/ingest", json=good(device_id="router-7")).status_code == 422
    # uppercase MAC with padding is normalised, then accepted and stored lower-case
    assert client.post("/ingest", json=good(device_id=f"  {MAC.upper()} ")).status_code == 200
    stored = client.get("/logs/recent").json()["data"][0]["device_id"]
    assert stored == MAC


# ---------- batch endpoint ----------
def test_batch_mixed_valid_and_invalid(client):
    missing = good(ts=2.0)
    missing.pop("device_id")
    r = client.post("/ingest/batch", json={"records": [good(ts=1.0), good(ts=3.0, humidity=150.0), missing]})
    body = r.json()
    assert r.status_code == 200
    assert (body["received"], body["accepted"], body["duplicates"], body["rejected"]) == (3, 1, 0, 2)
    assert len(body["sample_errors"]) == 2


def test_batch_is_idempotent(client):
    batch = {"records": [good(ts=float(i)) for i in range(1, 11)]}
    first = client.post("/ingest/batch", json=batch).json()
    second = client.post("/ingest/batch", json=batch).json()
    assert first["accepted"] == 10 and first["duplicates"] == 0
    assert second["accepted"] == 0 and second["duplicates"] == 10
    assert metrics(client)["totals"]["stored"] == 10


def test_batch_duplicate_inside_same_batch(client):
    r = client.post("/ingest/batch", json={"records": [good(ts=5.0), good(ts=5.0)]}).json()
    assert r["accepted"] == 1 and r["duplicates"] == 1


def test_batch_envelope_validation(client):
    assert client.post("/ingest/batch", json={"records": []}).status_code == 422
    assert client.post("/ingest/batch", json={"wrong": 1}).status_code == 422


# ---------- metrics ----------
def test_metrics_totals_and_error_rate(client):
    records = [good(ts=float(i)) for i in range(1, 9)]          # 8 valid
    records += [good(ts=100.0, humidity=150.0), good(ts=101.0, temp="x")]  # 2 invalid
    client.post("/ingest/batch", json={"records": records})
    m = metrics(client)
    assert m["totals"] == {"received": 10, "stored": 8, "rejected": 2}
    assert m["error_rate_pct"] == 20.0
    assert m["unique_devices"] == 1
    assert m["throughput"]["records_in_window"] == 10


# ---------- recent logs ----------
def test_recent_logs_newest_first_and_limit_validation(client):
    client.post("/ingest/batch", json={"records": [good(ts=100.0), good(ts=200.0), good(ts=150.0)]})
    data = client.get("/logs/recent?limit=2").json()
    assert data["count"] == 2
    assert [d["timestamp"] for d in data["data"]] == [200.0, 150.0]
    assert client.get("/logs/recent?limit=0").status_code == 422
