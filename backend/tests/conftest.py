from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app

# This fixture creates AND DROPS every table on whatever DATABASE_URL
# resolves to. Now that Settings correctly finds the repo-root .env
# regardless of cwd (see app/core/config.py), running `pytest` with no
# override would, for the first time, actually reach a real remote
# database (e.g. Neon) instead of silently missing it — a real risk that
# didn't used to exist by accident. Refuse outright unless the host looks
# like a local/test database; CI's own Postgres service container is
# already exposed on localhost, so this doesn't affect CI.
_SAFE_TEST_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@pytest.fixture(scope="session")
def engine():
    host = urlparse(settings.DATABASE_URL.replace("+psycopg", "")).hostname
    if host not in _SAFE_TEST_HOSTS:
        pytest.exit(
            f"Refusing to run tests against DATABASE_URL host {host!r} — it "
            "doesn't look local. This fixture creates and drops every table, "
            "which would be destructive against a real/shared database. Point "
            "DATABASE_URL at a local Postgres instance to run tests, e.g.:\n"
            '  DATABASE_URL="postgresql+psycopg://pulseiq:pulseiq@localhost:5432/pulseiq" pytest',
            returncode=1,
        )
    engine = create_engine(settings.DATABASE_URL, future=True)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    TestSessionLocal = sessionmaker(bind=connection, future=True)
    session = TestSessionLocal()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
