"""FastAPI application factory for Voice Scheduling Agent.

This module creates and configures the FastAPI application instance,
registering routers and middleware without business logic.
"""

from typing import Any

from fastapi import FastAPI

from core.config import get_settings
from routers.create_event import router as create_event_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance ready for uvicorn.
    """
    settings = get_settings()

    # Disable docs in production for security
    is_production = settings.environment.lower() == "production"

    app = FastAPI(
        title="Voice Scheduling Agent",
        description="Webhook server for voice AI calendar integration",
        version="0.1.0",
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else "/openapi.json",
    )

    # Register routers
    app.include_router(create_event_router, prefix="/create-event", tags=["webhooks"])

    @app.get("/healthz", tags=["health"])
    async def health_check() -> dict[str, Any]:
        """Health check endpoint for monitoring.

        Returns:
            dict: Status message indicating service health.
        """
        return {"status": "ok"}

    return app


# Global app instance for uvicorn
app = create_app()
