import os
import tempfile
from pathlib import Path

# Must happen BEFORE src.database is imported: tests use their own throwaway DB,
# never your real telemetry.db or Supabase. (load_dotenv does not override existing vars.)
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_tmp, 'test.db').as_posix()}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from src.database import Base, engine  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture()
def client():
    """Fresh, empty tables for every test; the lifespan handler recreates them on startup."""
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c
