import os

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text,
    UniqueConstraint, create_engine, func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# Load environment variables from .env file
load_dotenv()

# Read DATABASE_URL from environment, fallback to local SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./telemetry.db")

# Fix Supabase / PostgreSQL URI prefix quirk if present
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configure engine arguments based on database type
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    # pool_pre_ping: drop dead connections instead of failing a request
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()



class TelemetryLogModel(Base):
    """Validated telemetry readings. (device_id, timestamp) is unique -> idempotent loads."""
    __tablename__ = "telemetry_logs"
    __table_args__ = (UniqueConstraint("device_id", "timestamp", name="uq_device_ts"),)

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    device_id = Column(String, index=True, nullable=False)
    co = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    light = Column(Boolean, nullable=False)
    lpg = Column(Float, nullable=False)
    motion = Column(Boolean, nullable=False)
    smoke = Column(Float, nullable=False)
    temp = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    

class RejectedLogModel(Base):
    """Quarantine table: raw payloads that failed validation, plus the reason."""
    __tablename__ = "rejected_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    raw_payload = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

def init_db():
    """Initialize database tables in Supabase / PostgreSQL or SQLite."""
    Base.metadata.create_all(bind=engine)

def get_insert():
    """Dialect-specific INSERT that supports ON CONFLICT DO NOTHING."""
    if engine.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert