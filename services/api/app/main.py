from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


def create_app() -> FastAPI:
    app = FastAPI(
        title="Quiz Platform API",
        description=(
            "Образовательная платформа для создания опросов с AI-аналитикой.\n\n"
            "**Аутентификация**: передавайте заголовок `X-User-Id` с внешним ID пользователя "
            "(например, VK ID). Роль пользователя определяется автоматически."
        ),
        version="0.1.0",
        debug=settings.API_DEBUG,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()
