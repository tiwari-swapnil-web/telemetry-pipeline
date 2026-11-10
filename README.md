# Telemetry Ingestion & Validation Pipeline

A production-grade, asynchronous event ingestion and validation microservice modeled after high-throughput architectures at Ericsson. Built to demonstrate resilient backend engineering, strict data quality enforcement, and real-time operational observability.

---

## 🏗️ Architecture & Data Flow

```text
 [ IoT Dataset (CSV) ] 
         │
         ▼ (Streaming Producer with Anomaly Injection)
   [ generator.py ] 
         │
         ▼ HTTP POST /ingest
   [ FastAPI Microservice ] 
         │
         ├── Pydantic v2 (Strict Schema Validation & Sanitization)
         ├── SQLAlchemy ORM (Relational Persistence)
         │
         ▼
   [ SQLite / PostgreSQL DB ] ◄── GET /metrics (Real-time Analytics)

```
## 🚀 Tech Stack
Language: Python 3.10+
Backend Framework: FastAPI, Uvicorn
Data Validation: Pydantic v2
Database & ORM: SQLAlchemy (SQLite for local dev, PostgreSQL/Supabase ready)
Data Processing: Pandas, Requests


## 📂 Project Structure
```text
telemetry-pipeline/
├── data/
│   └── iot_telemetry_data.csv       # Smart building environmental dataset
├── src/
│   ├── __init__.py
│   ├── database.py                  # SQLAlchemy engine & session management
│   ├── generator.py                 # Streaming log producer & anomaly injector
│   ├── schemas.py                   # Pydantic v2 validation models
│   └── main.py                      # FastAPI application & endpoints
├── main.py                          # Application entry point
├── requirements.txt                 # Project dependencies
└── README.md
```
