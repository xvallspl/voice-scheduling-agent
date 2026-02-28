"""Authentication tests.

Tests for bearer token validation and security dependencies.
"""

import os
from typing import Generator

import pytest
from fastapi import Depends, FastAPI, status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from core.config import _load_settings
from core.security import BearerAuth


# Test configuration
TEST_WEBHOOK_SECRET = "test_webhook_secret_1234567890"  # 29 chars


@pytest.fixture(autouse=True)
def mock_env() -> Generator[None, None, None]:
    """Set up test environment variables."""
    original_secret = os.environ.get("WEBHOOK_SECRET")
    os.environ["WEBHOOK_SECRET"] = TEST_WEBHOOK_SECRET

    # Reset settings singleton
    import core.config

    core.config._settings = None

    yield

    # Restore original environment
    if original_secret is not None:
        os.environ["WEBHOOK_SECRET"] = original_secret
    else:
        # Only delete if it exists (may have been deleted by test)
        if "WEBHOOK_SECRET" in os.environ:
            del os.environ["WEBHOOK_SECRET"]
    core.config._settings = None


@pytest.fixture
def auth() -> BearerAuth:
    """Create a fresh BearerAuth instance."""
    return BearerAuth()


@pytest.fixture
def test_app(auth: BearerAuth) -> FastAPI:
    """Create a test FastAPI app with protected endpoint."""
    app = FastAPI()

    @app.post("/protected")
    async def protected_endpoint(
        credentials: HTTPAuthorizationCredentials = Depends(auth),
    ) -> dict[str, bool]:
        return {"status": True, "authenticated": True}

    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create a test client."""
    return TestClient(test_app)


class TestBearerAuth:
    """Test suite for Bearer token authentication."""

    def test_missing_auth_header_returns_401(self, client: TestClient) -> None:
        """Missing Authorization header returns 401 with WWW-Authenticate."""
        response = client.post("/protected")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert "Authentication required" in response.json()["detail"]

    def test_invalid_bearer_token_returns_401(self, client: TestClient) -> None:
        """Invalid Bearer token returns 401 with WWW-Authenticate."""
        response = client.post(
            "/protected",
            headers={"Authorization": "Bearer wrong_token_1234567890123456"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert "Invalid token" in response.json()["detail"]

    def test_wrong_auth_scheme_returns_401(self, client: TestClient) -> None:
        """Wrong authentication scheme returns 401."""
        response = client.post(
            "/protected",
            headers={"Authorization": f"Basic {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.headers.get("WWW-Authenticate") == "Bearer"
        assert "Invalid authentication scheme" in response.json()["detail"]

    def test_valid_token_proceeds(self, client: TestClient) -> None:
        """Valid Bearer token allows request to proceed."""
        response = client.post(
            "/protected",
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["authenticated"] is True

    def test_missing_webhook_secret_fails(self) -> None:
        """Settings fail fast if WEBHOOK_SECRET is missing (no insecure fallback)."""
        # Save and remove the secret
        original_secret = os.environ.get("WEBHOOK_SECRET")
        if "WEBHOOK_SECRET" in os.environ:
            del os.environ["WEBHOOK_SECRET"]

        # Reset settings singleton
        import core.config

        core.config._settings = None

        with pytest.raises(ValueError, match="webhook_secret"):
            _load_settings()

        # Restore
        if original_secret is not None:
            os.environ["WEBHOOK_SECRET"] = original_secret
        core.config._settings = None

    def test_webhook_secret_too_short_fails(
        self,
    ) -> None:
        """Settings fail fast if WEBHOOK_SECRET is too short."""
        # Set a short secret
        original_secret = os.environ.get("WEBHOOK_SECRET")
        os.environ["WEBHOOK_SECRET"] = "short"

        # Reset settings singleton
        import core.config

        core.config._settings = None

        with pytest.raises(ValueError, match="at least 24 characters"):
            _load_settings()

        # Restore
        if original_secret is not None:
            os.environ["WEBHOOK_SECRET"] = original_secret
        else:
            del os.environ["WEBHOOK_SECRET"]
        core.config._settings = None
