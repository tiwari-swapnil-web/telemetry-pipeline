from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import time

from src.database import SessionLocal, init_db, TelemetryLogModel
from src.schemas import TelemetryPayload, TelemetryResponse

app = FastAPI(
    title="Telemetry Ingestion & Validation Microservice",
    description="Production-grade ingestion pipeline for IoT smart-building environmental telemetry.",
    version="1.0.0"
)

# Startup event to ensure database tables are created
@app.on_event("startup")
def startup_event():
    init_db()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/ingest", response_model=TelemetryResponse, status_code=status.HTTP_200_OK)
def ingest_telemetry(payload: TelemetryPayload, db: Session = Depends(get_db)):
    """
    Ingests a single telemetry payload, validates it against Pydantic rules,
    and persists the cleaned record into the relational database.
    """
    try:
        # Map validated Pydantic model to SQLAlchemy database model
        db_record = TelemetryLogModel(
            timestamp=payload.timestamp,
            device_id=payload.device_id,
            co=payload.co,
            humidity=payload.humidity,
            light=payload.light,
            lpg=payload.lpg,
            motion=payload.motion,
            smoke=payload.smoke,
            temp=payload.temp
        )

        db.add(db_record)
        db.commit()
        db.refresh(db_record)

        return {
            "status": "success",
            "message": "Telemetry record successfully validated and stored.",
            "record_id": db_record.id
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Database insertion failed: {str(e)}"
        )

@app.get("/metrics", status_code=status.HTTP_200_OK)
def get_pipeline_metrics(db: Session = Depends(get_db)):
    """
    Calculates operational metrics across ingested telemetry records:
    - Total records processed
    - Unique active devices
    - System-wide averages (Temperature, Humidity, CO, Smoke)
    """
    total_records = db.query(func.count(TelemetryLogModel.id)).scalar() or 0

    if total_records == 0:
        return {
            "total_records_processed": 0,
            "unique_devices": 0,
            "averages": {}
        }

    unique_devices = db.query(func.count(func.distinct(TelemetryLogModel.device_id))).scalar() or 0
    
    # Query returning a Row object
    row = db.query(
        func.avg(TelemetryLogModel.temp).label("avg_temp"),
        func.avg(TelemetryLogModel.humidity).label("avg_humidity"),
        func.avg(TelemetryLogModel.co).label("avg_co"),
        func.avg(TelemetryLogModel.smoke).label("avg_smoke")
    ).first()

    if not row:
        averages = {"temperature_celsius": 0, "humidity_pct": 0, "carbon_monoxide": 0, "smoke": 0}
    else:
        # Use safe indexing or tuple unpacking to completely bypass attribute lookup warnings
        avg_temp, avg_humidity, avg_co, avg_smoke = row
        averages = {
            "temperature_celsius": round(avg_temp, 2) if avg_temp is not None else 0,
            "humidity_pct": round(avg_humidity, 2) if avg_humidity is not None else 0,
            "carbon_monoxide": round(avg_co, 4) if avg_co is not None else 0,
            "smoke": round(avg_smoke, 4) if avg_smoke is not None else 0
        }

    return {
        "total_records_processed": total_records,
        "unique_devices": unique_devices,
        "averages": averages
    }

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    return {"status": "healthy", "timestamp": time.time()}