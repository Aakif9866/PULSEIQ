"""The public-demo seeder (app/workers/seed_demo.py) — against the real
test database and real local-disk storage in a temp dir, including the
failure it most needs to survive: a redeploy wiping uploaded files while
their database rows remain."""
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import verify_password
from app.models.dashboard import Dashboard, DashboardChart
from app.models.dataset import Dataset
from app.models.user import User
from app.storage.local import LocalStorageProvider
from app.workers import seed_demo as seed_module
from app.workers.seed_demo import DEMO_DASHBOARD_NAME, DEMO_FILENAME, seed_demo

EMAIL = "demo-seed@pulseiq.dev"


@pytest.fixture()
def storage(tmp_path):
    return LocalStorageProvider(str(tmp_path))


@pytest.fixture(autouse=True)
def _demo_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DEMO_USER_EMAIL", EMAIL)
    monkeypatch.setattr(settings, "DEMO_USER_PASSWORD", "Demo-Pass-1")
    monkeypatch.setattr(settings, "LOCAL_STORAGE_ROOT", str(tmp_path))


def _user(db):
    return db.execute(select(User).where(User.email == EMAIL)).scalar_one_or_none()


def _demo_datasets(db, owner_id):
    return db.execute(
        select(Dataset).where(
            Dataset.owner_id == owner_id, Dataset.original_filename == DEMO_FILENAME
        )
    ).scalars().all()


def _demo_charts(db, owner_id):
    dashboard = db.execute(
        select(Dashboard).where(
            Dashboard.owner_id == owner_id, Dashboard.name == DEMO_DASHBOARD_NAME
        )
    ).scalars().all()
    assert len(dashboard) == 1
    return db.execute(
        select(DashboardChart).where(DashboardChart.dashboard_id == dashboard[0].id)
    ).scalars().all()


def test_does_nothing_when_not_configured(db_session, storage, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_USER_EMAIL", None)
    assert seed_demo(db_session, storage) is False
    assert _user(db_session) is None


def test_first_run_creates_user_profiled_dataset_and_dashboard(db_session, storage):
    assert seed_demo(db_session, storage) is True

    user = _user(db_session)
    assert user is not None
    (dataset,) = _demo_datasets(db_session, user.id)
    assert dataset.status == "profiled"
    assert dataset.row_count == 120
    assert storage.exists(dataset.storage_key)
    (chart,) = _demo_charts(db_session, user.id)
    assert chart.dataset_id == dataset.id


def test_rerunning_is_idempotent(db_session, storage):
    seed_demo(db_session, storage)
    user = _user(db_session)
    first_id = _demo_datasets(db_session, user.id)[0].id

    seed_demo(db_session, storage)
    seed_demo(db_session, storage)

    datasets = _demo_datasets(db_session, user.id)
    assert [d.id for d in datasets] == [first_id]  # not re-uploaded
    assert len(_demo_charts(db_session, user.id)) == 1  # not duplicated


def test_repairs_a_dataset_whose_file_a_redeploy_wiped(db_session, storage):
    # The real local-disk failure mode (docs/STORAGE.md): the row survives
    # a redeploy, the file doesn't. The dataset still *lists* fine but
    # can't be loaded — the seeder must notice and replace it.
    seed_demo(db_session, storage)
    user = _user(db_session)
    (broken,) = _demo_datasets(db_session, user.id)
    broken_id = broken.id
    storage.delete(broken.storage_key)

    seed_demo(db_session, storage)

    (repaired,) = _demo_datasets(db_session, user.id)
    assert repaired.id != broken_id
    assert storage.exists(repaired.storage_key)
    (chart,) = _demo_charts(db_session, user.id)
    assert chart.dataset_id == repaired.id  # the old chart cascaded away with the old row


def test_restores_a_dataset_a_visitor_deleted(db_session, storage):
    seed_demo(db_session, storage)
    user = _user(db_session)
    from app.services.dataset_service import DatasetService

    demo_id = _demo_datasets(db_session, user.id)[0].id
    DatasetService(db_session, storage).delete_owned(demo_id, user.id)
    assert _demo_datasets(db_session, user.id) == []

    seed_demo(db_session, storage)

    assert len(_demo_datasets(db_session, user.id)) == 1


def test_rotating_the_demo_password_is_just_an_env_change(db_session, storage, monkeypatch):
    seed_demo(db_session, storage)
    monkeypatch.setattr(settings, "DEMO_USER_PASSWORD", "Rotated-Pass-2")

    seed_demo(db_session, storage)

    user = _user(db_session)
    assert verify_password("Rotated-Pass-2", user.hashed_password)
    assert not verify_password("Demo-Pass-1", user.hashed_password)


def test_a_seeding_failure_never_blocks_startup(monkeypatch):
    def _explode(*_a, **_k):
        raise RuntimeError("storage unreachable")

    monkeypatch.setattr(seed_module, "seed_demo", _explode)
    fake_session = type("FakeSession", (), {"close": lambda self: None})()
    monkeypatch.setattr(seed_module, "SessionLocal", lambda: fake_session)
    assert seed_module.main() == 0
