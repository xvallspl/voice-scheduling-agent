"""FastAPI application factory for Voice Scheduling Agent.

This module creates and configures the FastAPI application instance,
registering routers and middleware without business logic.
"""

from fastapi import FastAPI

from routers.create_event import router as create_event_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance ready for uvicorn.
    """
    app = FastAPI(
        title="Voice Scheduling Agent",
        description="Webhook server for voice AI calendar integration",
        version="0.1.0",
    )

    # Register routers
    app.include_router(create_event_router, prefix="/create-event", tags=["webhooks"])

    @app.get("/healthz", tags=["health"])
    async def health_check() -> dict:
        """Health check endpoint for monitoring.

        Returns:
            dict: Status message indicating service health.
        """
        return {"status": "ok"}

    return app


# Global app instance for uvicorn
app = create_app()
