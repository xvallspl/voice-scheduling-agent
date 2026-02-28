"""Router integration tests.

End-to-end tests for webhook endpoints with dependency injection.
"""

from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import create_app
from routers.create_event import get_calendar_service_dep
from services.calendar import CalendarServiceError, CalendarServiceInterface


@pytest.fixture
def mock_calendar_service() -> Generator[MagicMock, None, None]:
    """Mock calendar service for testing."""
    with patch("routers.create_event.get_calendar_service") as mock:
        service = MagicMock(spec=CalendarServiceInterface)
        mock.return_value = service
        yield service


@pytest.fixture
def test_client(mock_calendar_service: MagicMock) -> Generator[TestClient, None, None]:
    """Create test client with mocked dependencies."""
    app = create_app()

    # Override the dependency
    def get_mock_service() -> MagicMock:
        return mock_calendar_service

    app.dependency_overrides = {}
    app.dependency_overrides[get_calendar_service_dep] = get_mock_service

    with TestClient(app) as client:
        yield client


# Test webhook secret for authentication
TEST_WEBHOOK_SECRET = "test_webhook_secret_1234567890"  # 29 chars


@pytest.fixture(autouse=True)
def mock_env() -> Generator[None, None, None]:
    """Set up test environment variables."""
    import os

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
        if "WEBHOOK_SECRET" in os.environ:
            del os.environ["WEBHOOK_SECRET"]
    core.config._settings = None


class TestCreateEventSuccess:
    """Tests for successful webhook processing."""

    def test_single_tool_call_success(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Successful single tool call returns proper response."""
        from schemas.calendar import EventCreate, EventResponse

        # Setup mock response
        async def mock_create_event(event_data: EventCreate) -> EventResponse:
            return EventResponse(
                id="event_123",
                summary="Interview",
                start="2026-03-05T14:00:00+00:00",
                end="2026-03-05T15:00:00+00:00",
                link="https://calendar.google.com/event?eid=123",
            )

        mock_calendar_service.create_event = mock_create_event

        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "John Doe",
                                "date": "2026-03-05",
                                "time": "14:00",
                                "title": "Interview",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["toolCallId"] == "toolu_123"
        assert "John Doe" in result["results"][0]["result"]
        assert "Interview" in result["results"][0]["result"]

    def test_multiple_tool_calls_success(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Multiple tool calls are all processed."""
        from schemas.calendar import EventCreate, EventResponse

        call_count = 0

        async def mock_create_event(event_data: EventCreate) -> EventResponse:
            nonlocal call_count
            call_count += 1
            return EventResponse(
                id=f"event_{call_count}",
                summary=event_data.title or "Meeting",
                start="2026-03-05T14:00:00+00:00",
                end="2026-03-05T15:00:00+00:00",
            )

        mock_calendar_service.create_event = mock_create_event

        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "User1",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    },
                    {
                        "id": "toolu_456",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "User2",
                                "date": "2026-03-06",
                                "time": "15:00",
                            },
                        },
                    },
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert len(result["results"]) == 2
        assert result["results"][0]["toolCallId"] == "toolu_123"
        assert result["results"][1]["toolCallId"] == "toolu_456"
        assert call_count == 2

    def test_without_title_uses_default(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Event without title uses default title from settings."""
        from schemas.calendar import EventCreate, EventResponse

        async def mock_create_event(event_data: EventCreate) -> EventResponse:
            # Verify title is None in event_data
            assert event_data.title is None
            return EventResponse(
                id="event_123",
                summary="Meeting",  # Default title
                start="2026-03-05T14:00:00+00:00",
                end="2026-03-05T15:00:00+00:00",
            )

        mock_calendar_service.create_event = mock_create_event

        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Jane Smith",
                                "date": "2026-03-05",
                                "time": "14:00",
                                # No title provided
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200


class TestCreateEventErrors:
    """Tests for error handling and edge cases."""

    def test_unknown_function_name_returns_safe_message(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Unknown function name returns voice-friendly error."""
        # Use valid EventCreate arguments but with unknown function name
        # Schema enforces EventCreate structure on all function calls
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "unknown_function",
                            "arguments": {
                                "name": "Test User",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200  # Still returns 200 with error in result
        result = response.json()
        assert "unknown_function" in result["results"][0]["result"]
        assert "don't know how to handle" in result["results"][0]["result"].lower()

    def test_calendar_service_error_returns_safe_message(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Calendar service errors return safe, voice-friendly messages."""
        from schemas.calendar import EventCreate

        async def mock_create_error(event_data: EventCreate) -> None:
            raise CalendarServiceError(
                "Calendar authentication failed. Please check service account credentials."
            )

        mock_calendar_service.create_event = mock_create_error

        payload: dict[str, Any] = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test User",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "authentication failed" in result["results"][0]["result"].lower()
        # Verify no stack traces or internal details leaked
        assert "traceback" not in result["results"][0]["result"].lower()
        assert "exception" not in result["results"][0]["result"].lower()

    def test_missing_required_field_returns_safe_error(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Missing required field in arguments returns voice-friendly error."""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test User",
                                "date": "2026-03-05",
                                # Missing required 'time' field
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        # Should return 200 with error message in result
        assert response.status_code == 200
        result = response.json()
        assert "couldn't create the event" in result["results"][0]["result"].lower()
        assert "time" in result["results"][0]["result"].lower()

    def test_invalid_date_format_returns_safe_error(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Invalid date format returns voice-friendly error."""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test User",
                                "date": "05-03-2026",  # Wrong format
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "couldn't create the event" in result["results"][0]["result"].lower()
        assert "YYYY-MM-DD" in result["results"][0]["result"]

    def test_empty_tool_call_list_returns_safe_error(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Empty toolCallList returns voice-friendly error message."""
        payload: dict[str, Any] = {
            "message": {
                "toolCallList": []  # Empty list
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        # Should return 200 with error message in result (voice-friendly)
        assert response.status_code == 200
        result = response.json()
        assert len(result["results"]) == 1
        assert "couldn't understand" in result["results"][0]["result"].lower()
        assert result["results"][0]["toolCallId"] == "unknown"

    def test_malformed_request_returns_safe_error(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Malformed request body returns voice-friendly error."""
        # Missing required 'message' field entirely
        payload: dict[str, Any] = {"some_other_field": "value"}

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        # Should return 200 with error message in result (voice-friendly)
        assert response.status_code == 200
        result = response.json()
        assert len(result["results"]) == 1
        assert "couldn't understand" in result["results"][0]["result"].lower()
        assert result["results"][0]["toolCallId"] == "unknown"


class TestCreateEventAuth:
    """Tests for authentication on webhook endpoint."""

    def test_missing_auth_returns_401(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Missing Authorization header returns 401."""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post("/create-event", json=payload)

        assert response.status_code == 401

    def test_invalid_auth_returns_401(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Invalid bearer token returns 401."""
        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": "Bearer wrong_token_1234567890123456"},
        )

        assert response.status_code == 401

    def test_valid_auth_proceeds(
        self,
        test_client: TestClient,
        mock_calendar_service: MagicMock,
    ) -> None:
        """Valid authentication allows request to proceed."""
        from schemas.calendar import EventCreate, EventResponse

        async def mock_create_event(event_data: EventCreate) -> EventResponse:
            return EventResponse(
                id="event_123",
                summary="Meeting",
                start="2026-03-05T14:00:00+00:00",
                end="2026-03-05T15:00:00+00:00",
            )

        mock_calendar_service.create_event = mock_create_event

        payload = {
            "message": {
                "toolCallList": [
                    {
                        "id": "toolu_123",
                        "function": {
                            "name": "create_calendar_event",
                            "arguments": {
                                "name": "Test",
                                "date": "2026-03-05",
                                "time": "14:00",
                            },
                        },
                    }
                ]
            }
        }

        response = test_client.post(
            "/create-event",
            json=payload,
            headers={"Authorization": f"Bearer {TEST_WEBHOOK_SECRET}"},
        )

        assert response.status_code == 200
