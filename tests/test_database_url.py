from src.database import normalise_database_url


def test_postgres_urls_get_an_explicit_driver():
    # SQLAlchemy 2.1 defaults "postgresql://" to psycopg 3; we install psycopg2-binary.
    assert normalise_database_url("postgres://u:p@h:5432/db") == "postgresql+psycopg2://u:p@h:5432/db"
    assert normalise_database_url("postgresql://u:p@h:5432/db") == "postgresql+psycopg2://u:p@h:5432/db"


def test_explicit_drivers_and_sqlite_are_left_alone():
    assert normalise_database_url("postgresql+psycopg://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalise_database_url("sqlite:///./telemetry.db") == "sqlite:///./telemetry.db"
