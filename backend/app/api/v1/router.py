from fastapi import APIRouter

from app.api.v1 import analysis, auth, dashboards, datasets, health, insights

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(datasets.router)
api_router.include_router(analysis.router)
api_router.include_router(insights.router)
api_router.include_router(dashboards.router)
