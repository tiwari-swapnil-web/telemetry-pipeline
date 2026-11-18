import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from typing import cast
from sqlalchemy.engine import CursorResult

from src.database import (
    RejectedLogModel, SessionLocal, TelemetryLogModel, get_insert, init_db,
)
from src.schemas import (
    BatchRequest, BatchResponse, RecentLogsResponse,
    TelemetryPayload, TelemetryResponse,
)


log = logging.getLogger("telemetry")

# Plain `def` endpoints below: the DB driver is blocking, so FastAPI runs them
# in its threadpool instead of stalling the event loop.

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Telemetry Ingestion & Validation Microservice",
    description="Validation-first ingestion pipeline for IoT environmental telemetry.",
    version="1.1.0",
    lifespan=lifespan,
)

# Startup event to ensure database tables are created (OBSOLETE)
#@app.on_event("startup")
#def startup_event():
#    init_db()


payload_adapter = TypeAdapter(TelemetryPayload)
INSERT_CHUNK = 500  # rows per INSERT statement; stays under DB bind-parameter limits

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# ---------- helpers ----------
def _fmt_errors(errors) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in errors)


def _save_rejects(items: list[tuple]) -> None:
    with SessionLocal() as db:
        db.add_all([
            RejectedLogModel(raw_payload=json.dumps(raw, default=str)[:4000], reason=reason[:1000])
            for raw, reason in items
        ])
        db.commit()



# ---------- quarantine single-record validation failures ----------
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc: RequestValidationError):
    if request.url.path == "/ingest":
        try:
            await run_in_threadpool(_save_rejects, [(exc.body, _fmt_errors(exc.errors()))])
        except Exception:
            log.exception("Could not store rejected record")
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})



# ---------- ingestion ----------
@app.post("/ingest", response_model=TelemetryResponse, status_code=status.HTTP_200_OK)
def ingest_telemetry(payload: TelemetryPayload, db: Session = Depends(get_db)):
    """Ingest ONE validated record. Use /ingest/batch for throughput."""
    try:
        record = TelemetryLogModel(**payload.model_dump())
        db.add(record)
        db.flush()               # assigns record.id without a second SELECT
        record_id = record.id
        db.commit()
        return {"status": "success",
                "message": "Telemetry record successfully validated and stored.",
                "record_id": record_id}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Record already exists for this device and timestamp.")
    except Exception:
        db.rollback()
        log.exception("Insert failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Internal error while storing record.")

'''
@app.post("/ingest/batch", response_model=BatchResponse)
def ingest_batch(batch: BatchRequest, db: Session = Depends(get_db)):
    valid, rejects, sample = [], [], []
    for i, raw in enumerate(batch.records):
        try:
            valid.append(payload_adapter.validate_python(raw).model_dump())
        except ValidationError as e:
            reason = _fmt_errors(e.errors())
            rejects.append({"raw_payload": json.dumps(raw, default=str)[:4000], "reason": reason[:1000]})
            if len(sample) < 20:
                sample.append({"index": i, "error": reason})
    try:
        if valid:
            db.execute(insert(TelemetryLogModel), valid)
        if rejects:
            db.execute(insert(RejectedLogModel), rejects)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Database insertion failed")
    return {"received": len(batch.records), "accepted": len(valid),
            "rejected": len(rejects), "sample_errors": sample}
'''


@app.post("/ingest/batch", response_model=BatchResponse)
def ingest_batch(batch: BatchRequest, db: Session = Depends(get_db)):
    """Validate each record individually; bulk-insert the valid ones, quarantine the rest."""
    valid, rejects, sample = [], [], []
    for i, raw in enumerate(batch.records):
        try:
            valid.append(payload_adapter.validate_python(raw).model_dump())
        except ValidationError as e:
            reason = _fmt_errors(e.errors())
            rejects.append({"raw_payload": json.dumps(raw, default=str)[:4000],
                            "reason": reason[:1000]})
            if len(sample) < 20:
                sample.append({"index": i, "error": reason})

    inserted = 0
    try:
        ins = get_insert()
        for i in range(0, len(valid), INSERT_CHUNK):
            stmt = ins(TelemetryLogModel).values(valid[i:i + INSERT_CHUNK]).on_conflict_do_nothing()
            result = cast(CursorResult, db.execute(stmt))
            inserted += result.rowcount or 0             # rows actually inserted
        if rejects:
            db.execute(insert(RejectedLogModel), rejects)
        db.commit()                                      # one atomic transaction
    except Exception:
        db.rollback()
        log.exception("Batch insert failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Database insertion failed")

    return {"received": len(batch.records), "accepted": inserted,
            "duplicates": len(valid) - inserted, "rejected": len(rejects),
            "sample_errors": sample}




# ---------- monitoring ----------
@app.get("/metrics", status_code=status.HTTP_200_OK)
def get_pipeline_metrics(db: Session = Depends(get_db)):
    """Totals, error rate, rolling throughput and sensor averages."""
    stored = db.query(func.count(TelemetryLogModel.id)).scalar() or 0
    rejected = db.query(func.count(RejectedLogModel.id)).scalar() or 0
    received = stored + rejected   # duplicates skipped by the unique key are not counted

    window = 60
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window)
    recent = db.query(func.count(TelemetryLogModel.id)).filter(
        TelemetryLogModel.created_at >= cutoff).scalar() or 0
    recent_rej = db.query(func.count(RejectedLogModel.id)).filter(
        RejectedLogModel.created_at >= cutoff).scalar() or 0

    row = db.query(
        func.count(func.distinct(TelemetryLogModel.device_id)),
        func.avg(TelemetryLogModel.temp),
        func.avg(TelemetryLogModel.humidity),
        func.avg(TelemetryLogModel.co),
        func.avg(TelemetryLogModel.smoke),
    ).first()
    devices, avg_t, avg_h, avg_co, avg_s = row if row else (0, None, None, None, None)

    def rnd(v, n=2):
        return round(v, n) if v is not None else None

    return {
        "totals": {"received": received, "stored": stored, "rejected": rejected},
        "error_rate_pct": round(100 * rejected / received, 2) if received else 0.0,
        "throughput": {
            "window_seconds": window,
            "records_in_window": recent + recent_rej,
            "records_per_sec": round((recent + recent_rej) / window, 2),
        },
        "unique_devices": devices,
        "averages": {
            "temperature_celsius": rnd(avg_t),
            "humidity_pct": rnd(avg_h),
            "carbon_monoxide": rnd(avg_co, 4),
            "smoke": rnd(avg_s, 4),
        },
    }


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/logs/recent", response_model=RecentLogsResponse)
def get_recent_logs(limit: int = Query(10, ge=1, le=500), db: Session = Depends(get_db)):
    """Most recent validated telemetry records."""
    logs = (db.query(TelemetryLogModel)
              .order_by(TelemetryLogModel.timestamp.desc()).limit(limit).all())
    return {"count": len(logs), "data": logs}