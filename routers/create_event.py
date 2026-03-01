"""Create Event webhook endpoint.

This module implements the /create-event webhook endpoint that receives
Vapi tool calls and orchestrates calendar event creation.
"""

import time
from collections import defaultdict

from fastapi import APIRouter, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from core.logging import get_logger
from core.security import bearer_auth
from schemas.calendar import EventCreate
from schemas.vapi import (
    ToolCallFunction,
    VapiRequest,
    VapiResponse,
    VapiResult,
)
from services.calendar import (
    CalendarServiceError,
    CalendarServiceInterface,
    get_calendar_service,
)

logger = get_logger(__name__)

router = APIRouter()

# Simple in-memory rate limiter: {ip: [(timestamp, count), ...]}
# Production would use Redis or similar distributed store
_rate_limit_store: dict[str, list[tuple[float, int]]] = defaultdict(list)
_MAX_REQUESTS_PER_MINUTE = 30  # 30 requests per minute per IP
_RATE_LIMIT_WINDOW = 60  # 60 seconds


def _check_rate_limit(client_ip: str) -> bool:
    """Check if client IP has exceeded rate limit.

    Args:
        client_ip: Client IP address

    Returns:
        bool: True if allowed, False if rate limited
    """
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW

    # Clean old entries and count current window requests
    requests = _rate_limit_store[client_ip]
    _rate_limit_store[client_ip] = [r for r in requests if r[0] > window_start]

    current_count = len(_rate_limit_store[client_ip])

    if current_count >= _MAX_REQUESTS_PER_MINUTE:
        return False

    # Record this request
    _rate_limit_store[client_ip].append((now, 1))
    return True


def get_calendar_service_dep() -> CalendarServiceInterface:
    """Dependency provider for calendar service.

    Returns:
        CalendarServiceInterface: Configured calendar service instance
    """
    return get_calendar_service()


async def process_tool_call(
    tool_call_id: str,
    function: ToolCallFunction,
    calendar_service: CalendarServiceInterface,
) -> VapiResult:
    """Process a single tool call.

    Args:
        tool_call_id: The ID of the tool call for response correlation
        function: The function call details
        calendar_service: Calendar service for event creation

    Returns:
        VapiResult: Result for this tool call
    """
    function_name = function.name
    raw_arguments = function.arguments

    # Handle unknown function names gracefully
    if function_name != "create_calendar_event":
        logger.warning(f"Unknown function name: {function_name}")
        return VapiResult(
            toolCallId=tool_call_id,
            result=f"I'm sorry, I don't know how to handle the function '{function_name}'. "
            "Please try again with a supported command.",
        )

    # Validate arguments as EventCreate for known function
    try:
        event_data = EventCreate(**raw_arguments)
    except ValidationError as e:
        logger.warning(f"Invalid arguments for {function_name}: {e}")
        # Extract first error message for voice-friendly response
        error_msg = str(e.errors()[0]["msg"]) if e.errors() else "Invalid parameters"
        return VapiResult(
            toolCallId=tool_call_id,
            result=f"I couldn't create the event because {error_msg}. "
            "Please provide the date in YYYY-MM-DD format and time in HH:MM format.",
        )

    try:
        # Create the calendar event
        event_response = await calendar_service.create_event(event_data)

        # Format user-friendly success message
        # Extract time from ISO datetime for readability
        start_iso = event_response.start
        # Parse ISO format to extract readable time
        # Format: 2026-03-05T14:00:00+00:00
        time_part = (
            start_iso.split("T")[1][:5] if "T" in start_iso else "the scheduled time"
        )
        date_part = (
            start_iso.split("T")[0] if "T" in start_iso else event_response.start
        )

        result_message = (
            f"Great! I've scheduled your meeting '{event_response.summary}' "
            f"with {event_data.name} on {date_part} at {time_part}. "
        )

        if event_response.link:
            result_message += f"You can view it here: {event_response.link}"

        return VapiResult(
            toolCallId=tool_call_id,
            result=result_message,
        )

    except CalendarServiceError as e:
        # Service layer already provides safe, user-friendly messages
        logger.error(
            f"Calendar service error for tool call {tool_call_id}: {e.message}"
        )
        return VapiResult(
            toolCallId=tool_call_id,
            result=e.message,
        )
    except Exception as e:
        # Catch-all for unexpected errors (should not happen)
        logger.error(
            f"Unexpected error processing tool call {tool_call_id}: {type(e).__name__}"
        )
        return VapiResult(
            toolCallId=tool_call_id,
            result="I'm sorry, I couldn't create the calendar event due to a technical issue. "
            "Please try again in a moment.",
        )


@router.post(
    "",
    response_model=VapiResponse,
    status_code=status.HTTP_200_OK,
    summary="Create calendar event from voice command",
    description="Receives Vapi tool calls and creates Google Calendar events.",
)
async def create_event(
    raw_request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_auth),
    calendar_service: CalendarServiceInterface = Depends(get_calendar_service_dep),
) -> VapiResponse:
    """Create calendar event from Vapi webhook.

    Processes incoming tool calls from Vapi voice assistants and
    creates corresponding Google Calendar events.

    Args:
        raw_request: Raw FastAPI request for flexible parsing
        credentials: Bearer token authentication (injected)
        calendar_service: Calendar service for event creation (injected)

    Returns:
        VapiResponse: Results for each tool call with toolCallId correlation
    """
    # Rate limiting check
    client_ip = raw_request.client.host if raw_request.client else "unknown"
    if not _check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return VapiResponse(
            results=[
                VapiResult(
                    toolCallId="unknown",
                    result="I'm sorry, there have been too many requests. "
                    "Please wait a moment and try again.",
                )
            ]
        )

    # Parse request body manually to handle malformed payloads gracefully
    try:
        body = await raw_request.json()
        request = VapiRequest(**body)
    except (RequestValidationError, ValidationError) as e:
        logger.warning(f"Invalid request format: {e}")
        # Return voice-friendly error for malformed request
        return VapiResponse(
            results=[
                VapiResult(
                    toolCallId="unknown",
                    result="I couldn't understand your request. Please make sure you provide "
                    "the meeting details including the person's name, date, and time.",
                )
            ]
        )
    except Exception as e:
        logger.error(f"Unexpected error parsing request: {type(e).__name__}")
        return VapiResponse(
            results=[
                VapiResult(
                    toolCallId="unknown",
                    result="I'm sorry, there was a problem processing your request. "
                    "Please try again with the meeting details.",
                )
            ]
        )

    results = []

    # Process each tool call in the request
    for tool_call in request.message.toolCallList:
        result = await process_tool_call(
            tool_call_id=tool_call.id,
            function=tool_call.function,
            calendar_service=calendar_service,
        )
        results.append(result)

    return VapiResponse(results=results)
