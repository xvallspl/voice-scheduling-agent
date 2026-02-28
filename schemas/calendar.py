"""Calendar event schemas.

This module defines Pydantic models for calendar event data
transfer between layers.
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class EventCreate(BaseModel):
    """DTO for creating a calendar event.

    Contains all required and optional fields for event creation
    as received from voice agent tool calls.
    """

    name: str = Field(
        ...,
        min_length=1,
        description="Attendee name",
    )
    date: str = Field(
        ...,
        min_length=10,
        max_length=10,
        description="Event date in YYYY-MM-DD format",
    )
    time: str = Field(
        ...,
        min_length=5,
        max_length=5,
        description="Event time in HH:MM format (24-hour)",
    )
    title: Optional[str] = Field(
        default=None,
        description="Optional meeting title (uses default if not provided)",
    )

    @field_validator("date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in YYYY-MM-DD format.

        Args:
            v: Date string to validate

        Returns:
            str: Validated date string

        Raises:
            ValueError: If date format is invalid
        """
        # Regex for YYYY-MM-DD format
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
        if not date_pattern.match(v):
            raise ValueError("date must be in YYYY-MM-DD format")

        # Try to parse to ensure valid date
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Invalid date: {e}")

        return v

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        """Validate time is in HH:MM format (24-hour).

        Args:
            v: Time string to validate

        Returns:
            str: Validated time string

        Raises:
            ValueError: If time format is invalid
        """
        # Regex for HH:MM format
        time_pattern = re.compile(r"^\d{2}:\d{2}$")
        if not time_pattern.match(v):
            raise ValueError("time must be in HH:MM format (24-hour)")

        # Try to parse to ensure valid time
        try:
            datetime.strptime(v, "%H:%M")
        except ValueError as e:
            raise ValueError(f"Invalid time: {e}")

        return v


class EventResponse(BaseModel):
    """DTO for calendar event creation response.

    Contains details of the created event for formatting
    user-friendly responses.
    """

    id: str = Field(
        ...,
        description="Google Calendar event ID",
    )
    summary: str = Field(
        ...,
        description="Event title/summary",
    )
    start: str = Field(
        ...,
        description="Event start time (ISO 8601)",
    )
    end: str = Field(
        ...,
        description="Event end time (ISO 8601)",
    )
    link: Optional[str] = Field(
        default=None,
        description="Link to the event in Google Calendar",
    )
