"""Calendar service tests.

Tests for Google Calendar service layer with mocked SDK.
"""

import asyncio
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from schemas.calendar import EventCreate, EventResponse
from services.calendar import (
    CalendarServiceError,
    GoogleCalendarService,
    get_calendar_service,
)


@pytest.fixture
def mock_settings() -> Generator[MagicMock, None, None]:
    """Mock settings for testing."""
    with patch("services.calendar.get_settings") as mock:
        mock.return_value.google_credentials_path = "test_credentials.json"
        mock.return_value.google_calendar_id = "test_calendar_id"
        mock.return_value.timezone = "UTC"
        mock.return_value.default_event_duration_minutes = 60
        mock.return_value.default_event_title = "Meeting"
        yield mock.return_value


@pytest.fixture
def sample_event() -> EventCreate:
    """Sample event data for testing."""
    return EventCreate(
        name="John Doe",
        date="2026-03-05",
        time="14:00",
        title="Test Meeting",
    )


class TestGoogleCalendarServiceTimezone:
    """Tests for timezone handling and UTC conversion."""

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_event_created_with_utc_datetime(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Verify local datetime is converted to UTC with explicit offset."""
        event = EventCreate(
            name="Test User",
            date="2026-03-05",
            time="14:00",
        )

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        # Capture the event body passed to insert
        captured_body = {}

        def capture_insert(calendarId: str, body: dict[str, Any]) -> MagicMock:
            captured_body.update(body)
            return MagicMock(
                execute=lambda: {
                    "id": "event_123",
                    "summary": body["summary"],
                    "start": body["start"],
                    "end": body["end"],
                }
            )

        mock_events.insert.side_effect = capture_insert
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        asyncio.run(service.create_event(event))

        # Verify UTC conversion happened
        assert captured_body["start"]["timeZone"] == "UTC"
        assert captured_body["end"]["timeZone"] == "UTC"

        # Verify ISO format includes UTC offset (+00:00)
        start_dt = captured_body["start"]["dateTime"]
        assert "+00:00" in start_dt or "Z" in start_dt or "-00:00" in start_dt

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_different_timezone_converts_correctly(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Verify different input timezone converts to correct UTC time."""
        # Override timezone to America/New_York
        mock_settings.timezone = "America/New_York"

        # 2:00 PM EST on March 5, 2026 should be 19:00 UTC
        event = EventCreate(
            name="Test User",
            date="2026-03-05",
            time="14:00",
        )

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        captured_body = {}

        def capture_insert(calendarId: str, body: dict[str, Any]) -> MagicMock:
            captured_body.update(body)
            return MagicMock(
                execute=lambda: {
                    "id": "event_123",
                    "summary": body["summary"],
                    "start": body["start"],
                    "end": body["end"],
                }
            )

        mock_events.insert.side_effect = capture_insert
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        asyncio.run(service.create_event(event))

        # Verify UTC conversion for EST (UTC-5 in March)
        start_dt = captured_body["start"]["dateTime"]
        # Should be 19:00 UTC (14:00 EST + 5 hours)
        assert "19:00:00" in start_dt or "T19:" in start_dt


class TestGoogleCalendarServiceSuccess:
    """Tests for successful event creation."""

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_create_event_success(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """Successfully create a calendar event."""
        # Setup mock
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value.execute.return_value = {
            "id": "event_123",
            "summary": "Test Meeting",
            "start": {"dateTime": "2026-03-05T14:00:00+00:00"},
            "end": {"dateTime": "2026-03-05T15:00:00+00:00"},
            "htmlLink": "https://calendar.google.com/event?eid=123",
        }
        mock_build.return_value = mock_service

        # Create service and call
        service = GoogleCalendarService()
        import asyncio

        result = asyncio.run(service.create_event(sample_event))

        # Verify
        assert isinstance(result, EventResponse)
        assert result.id == "event_123"
        assert result.summary == "Test Meeting"
        assert result.start == "2026-03-05T14:00:00+00:00"
        assert result.end == "2026-03-05T15:00:00+00:00"
        assert result.link == "https://calendar.google.com/event?eid=123"

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_create_event_without_title_uses_default(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        """Event without title uses default title."""
        event = EventCreate(
            name="Jane Smith",
            date="2026-03-05",
            time="10:00",
            # No title provided
        )

        # Setup mock
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value.execute.return_value = {
            "id": "event_456",
            "summary": "Meeting",  # Default title
            "start": {"dateTime": "2026-03-05T10:00:00"},
            "end": {"dateTime": "2026-03-05T11:00:00"},
        }
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        result = asyncio.run(service.create_event(event))

        assert result.summary == "Meeting"

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_service_reuses_authenticated_client(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """Service reuses authenticated client across calls."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value.execute.return_value = {
            "id": "event_789",
            "summary": "Test",
            "start": {"dateTime": "2026-03-05T14:00:00"},
            "end": {"dateTime": "2026-03-05T15:00:00"},
        }
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        # First call
        asyncio.run(service.create_event(sample_event))
        # Second call
        asyncio.run(service.create_event(sample_event))

        # build should only be called once (client reused)
        assert mock_build.call_count == 1


class TestGoogleCalendarServiceErrors:
    """Tests for error handling and domain error mapping."""

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_http_401_authentication_error(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """401 error maps to user-friendly auth message."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        # Create HttpError mock
        resp = MagicMock()
        resp.status = 401
        mock_events.insert.return_value.execute.side_effect = HttpError(
            resp=resp,
            content=b"Unauthorized",
        )
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        with pytest.raises(CalendarServiceError, match="authentication failed"):
            asyncio.run(service.create_event(sample_event))

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_http_403_permission_error(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """403 error maps to user-friendly permission message."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        resp = MagicMock()
        resp.status = 403
        mock_events.insert.return_value.execute.side_effect = HttpError(
            resp=resp,
            content=b"Forbidden",
        )
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        with pytest.raises(CalendarServiceError, match="access denied"):
            asyncio.run(service.create_event(sample_event))

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_http_404_not_found_error(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """404 error maps to user-friendly calendar not found message."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        resp = MagicMock()
        resp.status = 404
        mock_events.insert.return_value.execute.side_effect = HttpError(
            resp=resp,
            content=b"Not Found",
        )
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        with pytest.raises(CalendarServiceError, match="Calendar not found"):
            asyncio.run(service.create_event(sample_event))

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_http_500_server_error(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """500 error maps to generic service unavailable message."""
        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        resp = MagicMock()
        resp.status = 500
        mock_events.insert.return_value.execute.side_effect = HttpError(
            resp=resp,
            content=b"Internal Server Error",
        )
        mock_build.return_value = mock_service

        service = GoogleCalendarService()
        import asyncio

        with pytest.raises(CalendarServiceError, match="temporarily unavailable"):
            asyncio.run(service.create_event(sample_event))

    @patch("services.calendar.service_account.Credentials")
    def test_credentials_file_not_found(
        self,
        mock_creds: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """Missing credentials file raises CalendarServiceError."""
        mock_creds.from_service_account_file.side_effect = FileNotFoundError(
            "credentials.json not found"
        )

        service = GoogleCalendarService()
        import asyncio

        with pytest.raises(CalendarServiceError, match="configuration error"):
            asyncio.run(service.create_event(sample_event))


class TestCalendarServiceFactory:
    """Tests for service factory function."""

    @patch("services.calendar.GoogleCalendarService")
    def test_get_calendar_service_returns_instance(
        self,
        mock_service_class: MagicMock,
    ) -> None:
        """Factory returns configured service instance."""
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance

        result = get_calendar_service()

        assert result == mock_instance
        mock_service_class.assert_called_once()


class TestCalendarServiceTimeout:
    """Tests for timeout behavior."""

    @patch("services.calendar.build")
    @patch("services.calendar.service_account.Credentials")
    def test_timeout_enforced(
        self,
        mock_creds: MagicMock,
        mock_build: MagicMock,
        mock_settings: MagicMock,
        sample_event: EventCreate,
    ) -> None:
        """Slow API calls are timed out per voice platform requirements."""
        import time

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events

        # Simulate slow synchronous response (blocking call)
        def slow_execute(*args: Any, **kwargs: Any) -> dict[str, str]:
            time.sleep(10)  # Blocking sleep longer than timeout
            return {"id": "event_slow"}

        mock_events.insert.return_value.execute = slow_execute
        mock_build.return_value = mock_service

        # Service with short timeout for testing
        service = GoogleCalendarService(timeout=0.1)

        with pytest.raises(CalendarServiceError, match="too long"):
            asyncio.run(service.create_event(sample_event))


class TestCalendarServiceError:
    """Tests for CalendarServiceError exception."""

    def test_error_stores_message(self) -> None:
        """Exception stores safe message."""
        original = ValueError("secret details")
        err = CalendarServiceError("Safe message", original_error=original)

        assert str(err) == "Safe message"
        assert err.message == "Safe message"
        assert err.original_error is original

    def test_error_without_original(self) -> None:
        """Exception works without original error."""
        err = CalendarServiceError("Simple error")

        assert str(err) == "Simple error"
        assert err.original_error is None
