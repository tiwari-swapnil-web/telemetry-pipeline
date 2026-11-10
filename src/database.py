import os
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Automatically reads DATABASE_URL from environment; defaults to local SQLite
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./data/telemetry.db")

# Ensure local data directory exists if using SQLite
if DB_URL.startswith("sqlite"):
    os.makedirs("./data", exist_ok=True)

# Create SQLAlchemy engine
engine = create_engine(
    DB_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DB_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TelemetryLogModel(Base):
    __tablename__ = "telemetry_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(Float, index=True)
    device_id = Column(String(50), index=True)
    co = Column(Float)
    humidity = Column(Float)
    light = Column(Boolean)
    lpg = Column(Float)
    motion = Column(Boolean)
    smoke = Column(Float)
    temp = Column(Float)

def init_db():
    """Initializes database tables."""
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("Database and tables initialized successfully.")