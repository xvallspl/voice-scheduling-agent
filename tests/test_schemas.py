"""Schema validation tests.

Tests for Pydantic model validation and edge cases.
"""

import pytest
from pydantic import ValidationError

from schemas.vapi import (
    ToolCallFunction,
    ToolCallItem,
    VapiRequest,
    VapiResponse,
    VapiResult,
)
from schemas.calendar import EventCreate, EventResponse


class TestToolCallFunction:
    """Tests for ToolCallFunction schema."""

    def test_valid_function(self) -> None:
        """Create valid function schema."""
        func = ToolCallFunction(
            name="create_calendar_event",
            arguments=EventCreate(
                name="John",
                date="2026-03-05",
                time="14:00",
            ),
        )
        assert func.name == "create_calendar_event"
        assert func.arguments.name == "John"

    def test_arguments_as_dict(self) -> None:
        """Arguments can be passed as dict and validated."""
        func = ToolCallFunction(
            name="create_calendar_event",
            arguments={"name": "Jane", "date": "2026-04-10", "time": "09:00"},  # type: ignore[arg-type]
        )
        assert func.arguments.name == "Jane"
        assert func.arguments.date == "2026-04-10"


class TestToolCallItem:
    """Tests for ToolCallItem schema."""

    def test_valid_tool_call(self) -> None:
        """Create valid tool call item."""
        item = ToolCallItem(
            id="toolu_123",
            function=ToolCallFunction(
                name="create_calendar_event",
                arguments=EventCreate(name="John", date="2026-03-05", time="14:00"),
            ),
        )
        assert item.id == "toolu_123"
        assert item.function.name == "create_calendar_event"

    def test_empty_id_fails(self) -> None:
        """Empty tool call ID fails validation."""
        with pytest.raises(ValidationError, match="id"):
            ToolCallItem(
                id="",
                function=ToolCallFunction(
                    name="create_calendar_event",
                    arguments=EventCreate(name="test", date="2026-03-05", time="14:00"),
                ),
            )


class TestToolCallFunctionArguments:
    """Tests for ToolCallFunction argument contract validation."""

    def test_valid_arguments(self) -> None:
        """Valid function arguments pass validation."""
        func = ToolCallFunction(
            name="create_calendar_event",
            arguments=EventCreate(
                name="John Doe",
                date="2026-03-05",
                time="14:00",
                title="Interview",
            ),
        )
        assert func.arguments.name == "John Doe"
        assert func.arguments.title == "Interview"

    def test_arguments_without_title(self) -> None:
        """Arguments without optional title are valid."""
        func = ToolCallFunction(
            name="create_calendar_event",
            arguments=EventCreate(
                name="Jane Smith",
                date="2026-04-15",
                time="09:30",
            ),
        )
        assert func.arguments.title is None

    def test_missing_required_arguments_fails(self) -> None:
        """Missing required arguments (name, date, time) fails at Vapi level."""
        # Missing date in function arguments
        with pytest.raises(ValidationError, match="date"):
            ToolCallFunction(
                name="create_calendar_event",
                arguments={"name": "John", "time": "14:00"},  # type: ignore[arg-type]
            )

    def test_invalid_date_in_arguments_fails(self) -> None:
        """Invalid date format in function arguments fails validation."""
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            ToolCallFunction(
                name="create_calendar_event",
                arguments={
                    "name": "John",
                    "date": "05-03-2026",  # Wrong format
                    "time": "14:00",
                },  # type: ignore[arg-type]
            )

    def test_invalid_time_in_arguments_fails(self) -> None:
        """Invalid time format in function arguments fails validation."""
        # Use 5-char invalid format (passes length, fails regex)
        with pytest.raises(ValidationError, match="HH:MM"):
            ToolCallFunction(
                name="create_calendar_event",
                arguments={
                    "name": "John",
                    "date": "2026-03-05",
                    "time": "14-00",  # Wrong format (dash instead of colon)
                },  # type: ignore[arg-type]
            )


class TestVapiRequest:
    """Tests for VapiRequest schema."""

    def test_valid_request(self) -> None:
        """Parse valid Vapi request payload."""
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
                            },
                        },
                    }
                ]
            }
        }
        request = VapiRequest(**payload)  # type: ignore[arg-type]
        assert len(request.message.toolCallList) == 1
        assert request.message.toolCallList[0].id == "toolu_123"
        assert request.message.toolCallList[0].function.name == "create_calendar_event"

    def test_empty_tool_call_list_fails(self) -> None:
        """Empty toolCallList fails validation."""
        with pytest.raises(ValidationError, match="toolCallList"):
            VapiRequest(message={"toolCallList": []})  # type: ignore[arg-type]

    def test_missing_tool_call_list_fails(self) -> None:
        """Missing toolCallList defaults to empty and fails."""
        with pytest.raises(ValidationError, match="toolCallList"):
            VapiRequest(message={})  # type: ignore[arg-type]

    def test_multiple_tool_calls(self) -> None:
        """Request with multiple tool calls is valid."""
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
        request = VapiRequest(**payload)  # type: ignore[arg-type]
        assert len(request.message.toolCallList) == 2


class TestVapiResponse:
    """Tests for VapiResponse schema."""

    def test_valid_response(self) -> None:
        """Create valid Vapi response."""
        response = VapiResponse(
            results=[
                VapiResult(toolCallId="toolu_123", result="Event created successfully")
            ]
        )
        assert len(response.results) == 1
        assert response.results[0].toolCallId == "toolu_123"

    def test_empty_result_fails(self) -> None:
        """Empty result string fails validation."""
        with pytest.raises(ValidationError, match="result"):
            VapiResult(toolCallId="toolu_123", result="")

    def test_tool_call_id_propagation(self) -> None:
        """toolCallId is correctly propagated in response."""
        result = VapiResult(
            toolCallId="toolu_abc_456",
            result="Your meeting has been scheduled for March 5th at 2 PM",
        )
        assert result.toolCallId == "toolu_abc_456"


class TestEventCreate:
    """Tests for EventCreate schema."""

    def test_valid_event(self) -> None:
        """Create valid event DTO."""
        event = EventCreate(
            name="John Doe",
            date="2026-03-05",
            time="14:00",
        )
        assert event.name == "John Doe"
        assert event.date == "2026-03-05"
        assert event.time == "14:00"
        assert event.title is None

    def test_valid_event_with_title(self) -> None:
        """Create valid event DTO with optional title."""
        event = EventCreate(
            name="Jane Smith",
            date="2026-04-15",
            time="09:30",
            title="Team Meeting",
        )
        assert event.title == "Team Meeting"

    def test_missing_name_fails(self) -> None:
        """Missing required name field fails."""
        with pytest.raises(ValidationError, match="name"):
            EventCreate(date="2026-03-05", time="14:00")  # type: ignore[call-arg]

    def test_missing_date_fails(self) -> None:
        """Missing required date field fails."""
        with pytest.raises(ValidationError, match="date"):
            EventCreate(name="John", time="14:00")  # type: ignore[call-arg]

    def test_missing_time_fails(self) -> None:
        """Missing required time field fails."""
        with pytest.raises(ValidationError, match="time"):
            EventCreate(name="John", date="2026-03-05")  # type: ignore[call-arg]

    def test_invalid_date_format_fails(self) -> None:
        """Invalid date format fails validation."""
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            EventCreate(name="John", date="05-03-2026", time="14:00")

    def test_invalid_date_value_fails(self) -> None:
        """Invalid date value (e.g., Feb 30) fails validation."""
        with pytest.raises(ValidationError, match="Invalid date"):
            EventCreate(name="John", date="2026-02-30", time="14:00")

    def test_invalid_time_format_fails(self) -> None:
        """Invalid time format fails validation."""
        # Use 5-char invalid format (passes length, fails regex)
        with pytest.raises(ValidationError, match="HH:MM"):
            EventCreate(name="John", date="2026-03-05", time="14-00")

    def test_invalid_time_value_fails(self) -> None:
        """Invalid time value (e.g., 25:00) fails validation."""
        with pytest.raises(ValidationError, match="Invalid time"):
            EventCreate(name="John", date="2026-03-05", time="25:00")

    def test_edge_case_dates(self) -> None:
        """Edge case dates are handled correctly."""
        # Leap year
        event = EventCreate(name="Test", date="2024-02-29", time="12:00")
        assert event.date == "2024-02-29"

        # Year boundary
        event = EventCreate(name="Test", date="2026-12-31", time="23:59")
        assert event.date == "2026-12-31"


class TestEventResponse:
    """Tests for EventResponse schema."""

    def test_valid_response(self) -> None:
        """Create valid event response DTO."""
        response = EventResponse(
            id="abc123",
            summary="Team Meeting",
            start="2026-03-05T14:00:00",
            end="2026-03-05T15:00:00",
            link="https://calendar.google.com/event?eid=abc",
        )
        assert response.id == "abc123"
        assert response.link is not None

    def test_optional_link(self) -> None:
        """Link field is optional."""
        response = EventResponse(
            id="abc123",
            summary="Meeting",
            start="2026-03-05T14:00:00",
            end="2026-03-05T15:00:00",
        )
        assert response.link is None
