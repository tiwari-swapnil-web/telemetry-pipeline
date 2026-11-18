from pydantic import BaseModel, ConfigDict, Field, field_validator

class TelemetryPayload(BaseModel):
    """Strict schema for one telemetry reading."""
    timestamp: float = Field(..., description="Epoch timestamp of the reading")
    device_id: str = Field(..., pattern=r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$", description="Device MAC address")
    co: float = Field(..., ge=0.0, description="Carbon monoxide concentration")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Humidity percentage")
    light: bool = Field(..., description="Light sensor status")
    lpg: float = Field(..., ge=0.0, description="LPG concentration")
    motion: bool = Field(..., description="Motion detection status")
    smoke: float = Field(..., ge=0.0, description="Smoke concentration")
    temp: float = Field(..., ge=-50.0, le=150.0, description="Temperature in Celsius")

    # mode="before" -> normalise first, THEN the MAC pattern is checked
    @field_validator("device_id", mode="before")
    @classmethod
    def normalize_device_id(cls, v):
        return v.strip().lower() if isinstance(v, str) else v

class TelemetryResponse(BaseModel):
    status: str
    message: str
    record_id: int | None = None

class BatchRequest(BaseModel):
    # Raw dicts on purpose: each record is validated individually in the endpoint,
    # so one bad record never causes the whole batch to be rejected.
    records: list[dict] = Field(..., min_length=1, max_length=5000)

class BatchResponse(BaseModel):
    received: int
    accepted: int
    duplicates: int
    rejected: int
    sample_errors: list[dict] = []

class TelemetryRecordOut(TelemetryPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int

class RecentLogsResponse(BaseModel):
    count: int
    data: list[TelemetryRecordOut]