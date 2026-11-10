from pydantic import BaseModel, Field, field_validator

class TelemetryPayload(BaseModel):
    timestamp: float = Field(..., description="Epoch timestamp of the reading")
    device_id: str = Field(..., min_length=5, description="Device MAC address or identifier")
    co: float = Field(..., ge=0.0, description="Carbon monoxide concentration")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Humidity percentage")
    light: bool = Field(..., description="Light sensor status")
    lpg: float = Field(..., ge=0.0, description="LPG concentration")
    motion: bool = Field(..., description="Motion detection status")
    smoke: float = Field(..., description="Smoke concentration")
    temp: float = Field(..., ge=-50.0, le=150.0, description="Temperature reading in Celsius")

    @field_validator('device_id')
    def case_normalizer(cls, v: str) -> str:
        return v.strip().lower()

class TelemetryResponse(BaseModel):
    status: str
    message: str
    record_id: int | None = None