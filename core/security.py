"""Bearer token authentication dependencies.

This module provides FastAPI dependencies for validating webhook
authentication tokens with proper 401 responses.
"""

import secrets
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from core.config import get_settings


class BearerAuth(HTTPBearer):
    """Custom Bearer authentication with strict 401 handling.

    This class implements the authentication dependency that:
    - Returns 401 with proper WWW-Authenticate header for missing tokens
    - Returns 401 with proper WWW-Authenticate header for invalid tokens
    - Proceeds only with valid tokens matching WEBHOOK_SECRET
    """

    def __init__(self) -> None:
        """Initialize with auto_error=False to control 401 responses."""
        super().__init__(auto_error=False)

    async def __call__(
        self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        """Validate Bearer token from request.

        Args:
            request: The incoming request

        Returns:
            HTTPAuthorizationCredentials if valid, otherwise raises 401

        Raises:
            HTTPException: 401 with WWW-Authenticate header for missing/invalid tokens
        """
        # Check if Authorization header exists with wrong scheme first
        auth_header = request.headers.get("Authorization")
        if auth_header:
            scheme, _, _ = auth_header.partition(" ")
            if scheme.lower() != "bearer":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme. Use Bearer.",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        credentials = await super().__call__(request)

        if credentials is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        settings = get_settings()
        if not secrets.compare_digest(credentials.credentials, settings.webhook_secret):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return credentials


# Global auth instance for dependency injection
bearer_auth = BearerAuth()
