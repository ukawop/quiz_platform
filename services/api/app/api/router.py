from fastapi import APIRouter

from app.api.routers import users, surveys, responses, analytics

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(users.router)
api_router.include_router(surveys.router)
api_router.include_router(responses.router)
api_router.include_router(analytics.router)
