"""Import all ORM models here so Base.metadata is complete for Alembic
autogenerate and for create_all() in tests.
"""
from app.models.dashboard import Dashboard, DashboardChart
from app.models.dataset import Dataset
from app.models.insight import Insight
from app.models.user import User

__all__ = ["Dashboard", "DashboardChart", "Dataset", "Insight", "User"]
