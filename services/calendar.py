"""Google Calendar service implementation.

This module provides an async-safe interface to Google Calendar API,
including service account authentication and event creation.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

from core.config import get_settings
from core.logging import get_logger
from schemas.calendar import EventCreate, EventResponse

logger = get_logger(__name__)

# Default timeout for Google API calls (seconds)
# Voice providers drop calls if webhooks take too long
DEFAULT_API_TIMEOUT = 8.0


class CalendarServiceError(Exception):
    """Domain exception for calendar service failures.

    This exception provides safe, user-friendly error messages
    suitable for voice agents. Never exposes internal details
    or stack traces.
    """

    def __init__(
        self, message: str, original_error: Optional[Exception] = None
    ) -> None:
        """Initialize with safe message and optional original error.

        Args:
            message: Safe, user-friendly error message
            original_error: Original exception for logging (not exposed)
        """
        super().__init__(message)
        self.message = message
        self.original_error = original_error


class CalendarServiceInterface(ABC):
    """Abstract interface for calendar operations.

    Defines the contract for calendar service implementations,
    enabling dependency injection and testability.
    """

    @abstractmethod
    async def create_event(self, event_data: EventCreate) -> EventResponse:
        """Create a calendar event.

        Args:
            event_data: Event creation parameters

        Returns:
            EventResponse: Created event details

        Raises:
            CalendarServiceError: If event creation fails
        """
        pass


class GoogleCalendarService(CalendarServiceInterface):
    """Google Calendar API service implementation.

    Provides async-safe access to Google Calendar with:
    - Service account authentication
    - Blocking SDK calls wrapped in asyncio.to_thread()
    - Domain error mapping (no raw exceptions leak)
    - Configurable timeout for voice platform compatibility
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        calendar_id: Optional[str] = None,
        timeout: float = DEFAULT_API_TIMEOUT,
    ) -> None:
        """Initialize with configuration.

        Args:
            credentials_path: Path to service account JSON (defaults to settings)
            calendar_id: Calendar ID to use (defaults to settings)
            timeout: API call timeout in seconds
        """
        settings = get_settings()
        self._credentials_path = credentials_path or settings.google_credentials_path
        self._calendar_id = calendar_id or settings.google_calendar_id
        self._timeout = timeout
        self._timezone = settings.timezone
        self._default_duration = settings.default_event_duration_minutes
        self._default_title = settings.default_event_title
        self._service: Optional[Any] = None

    def _get_service(self) -> Any:
        """Get or create authenticated Google Calendar service.

        Returns:
            object: Authenticated Google Calendar API service

        Raises:
            CalendarServiceError: If authentication fails
        """
        if self._service is not None:
            return self._service

        try:
            credentials = service_account.Credentials.from_service_account_file(  # type: ignore[no-untyped-call]
                self._credentials_path,
                scopes=["https://www.googleapis.com/auth/calendar"],
            )
            self._service = build("calendar", "v3", credentials=credentials)
            return self._service
        except FileNotFoundError as e:
            logger.error(f"Credentials file not found: {self._credentials_path}")
            raise CalendarServiceError(
                "Calendar service configuration error",
                original_error=e,
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize Google Calendar service: {type(e).__name__}"
            )
            raise CalendarServiceError(
                "Calendar service initialization failed",
                original_error=e,
            )

    def _build_event_body(self, event_data: EventCreate) -> dict[str, Any]:
        """Build Google Calendar event body from DTO with UTC enforcement.

        Per SPEC/AGENTS.md: All date/time strings are treated as local to the
        configured timezone, then converted to explicit UTC ISO-8601 for
        Google Calendar API.

        Args:
            event_data: Event creation parameters

        Returns:
            dict: Google Calendar API event body with UTC datetimes
        """
        # Parse date and time as local to configured timezone
        date_str = event_data.date
        time_str = event_data.time

        # Build start datetime in configured timezone
        tz = ZoneInfo(self._timezone)
        start_local = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        start_local = start_local.replace(tzinfo=tz)

        # Convert to UTC
        start_utc = start_local.astimezone(timezone.utc)

        # Calculate end time based on default duration
        end_utc = start_utc + timedelta(minutes=self._default_duration)

        # Format for Google Calendar API (explicit UTC with offset)
        start_iso = start_utc.isoformat()
        end_iso = end_utc.isoformat()

        # Use provided title or default
        summary = event_data.title or self._default_title

        # Add attendee name to description
        description = f"Meeting with {event_data.name}"

        event_body = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_iso,
                "timeZone": "UTC",  # Explicit UTC timezone
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": "UTC",  # Explicit UTC timezone
            },
        }

        return event_body

    def _sync_create_event(self, event_data: EventCreate) -> EventResponse:
        """Synchronous event creation (to be run in thread).

        Args:
            event_data: Event creation parameters

        Returns:
            EventResponse: Created event details

        Raises:
            CalendarServiceError: If creation fails
        """
        service = self._get_service()
        event_body = self._build_event_body(event_data)

        try:
            result = (
                service.events()
                .insert(calendarId=self._calendar_id, body=event_body)
                .execute()
            )

            # Build response DTO
            response = EventResponse(
                id=result["id"],
                summary=result["summary"],
                start=result["start"]["dateTime"],
                end=result["end"]["dateTime"],
                link=result.get("htmlLink"),
            )

            logger.info(f"Created calendar event: {response.id}")
            return response

        except HttpError as e:
            logger.error(
                f"Google Calendar API error: {e.resp.status} - {e._get_reason()}"
            )
            if e.resp.status == 401:
                raise CalendarServiceError(
                    "Calendar authentication failed. Please check service account credentials.",
                    original_error=e,
                )
            elif e.resp.status == 403:
                raise CalendarServiceError(
                    "Calendar access denied. Please check calendar sharing permissions.",
                    original_error=e,
                )
            elif e.resp.status == 404:
                raise CalendarServiceError(
                    "Calendar not found. Please check the calendar ID configuration.",
                    original_error=e,
                )
            else:
                raise CalendarServiceError(
                    "Calendar service temporarily unavailable. Please try again.",
                    original_error=e,
                )
        except Exception as e:
            logger.error(f"Unexpected error creating event: {type(e).__name__}")
            raise CalendarServiceError(
                "Failed to create calendar event. Please try again.",
                original_error=e,
            )

    async def create_event(self, event_data: EventCreate) -> EventResponse:
        """Create a calendar event (async wrapper).

        Wraps the synchronous Google SDK call in asyncio.to_thread()
        to prevent blocking the event loop.

        Args:
            event_data: Event creation parameters

        Returns:
            EventResponse: Created event details

        Raises:
            CalendarServiceError: If event creation fails
        """
        # Use asyncio.wait_for to enforce timeout
        # Voice providers drop calls if webhooks take too long
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._sync_create_event, event_data),
                timeout=self._timeout,
            )
        except asyncio.TimeoutError as e:
            logger.error(f"Calendar API call timed out after {self._timeout}s")
            raise CalendarServiceError(
                "Calendar service is taking too long. Please try again.",
                original_error=e,
            )


def get_calendar_service() -> CalendarServiceInterface:
    """Factory function to get calendar service instance.

    Returns:
        CalendarServiceInterface: Configured calendar service
    """
    return GoogleCalendarService()
