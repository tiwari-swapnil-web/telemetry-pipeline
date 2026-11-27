import os
import tempfile
from pathlib import Path

# Must happen BEFORE src.database is imported. Tests never touch your real database:
#   - default: a throwaway SQLite file
#   - CI / local Postgres check: set TEST_DATABASE_URL to a LOCAL throwaway Postgres
# (load_dotenv does not override variables that are already set.)
_pg = os.environ.get("TEST_DATABASE_URL")
if _pg:
    # The client fixture DROPS ALL TABLES, so refuse anything that is not local.
    if "@localhost" not in _pg and "@127.0.0.1" not in _pg:
        raise RuntimeError("TEST_DATABASE_URL must point to localhost: the tests drop all tables.")
    os.environ["DATABASE_URL"] = _pg
else:
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
