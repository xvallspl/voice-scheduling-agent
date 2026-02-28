# Voice Scheduling Agent - Developer Guidelines

Python FastAPI webhook server integrating Google Calendar API with voice AI platforms (Vapi/Retell). See `SPEC.md` for full assignment requirements.

## Project Overview

| Component | Technology |
|-----------|------------|
| Framework | FastAPI with Uvicorn |
| Python | 3.12+ |
| Validation | Pydantic v2 |
| Calendar | Google API Python Client (Service Account) |
| Testing | pytest, pytest-asyncio, HTTPX, pytest-mock |
| Linting | Ruff, MyPy (strict mode) |

## Infrastructure & Deployment

### Hosting Setup (Critical)
- **Server:** Hetzner Linux VPS
- **Exposure:** Tailscale Funnel (local port → public HTTPS)
- **Important:** FastAPI runs on `0.0.0.0:8000` to allow the Funnel to route traffic. TLS termination is handled by Tailscale Funnel, NOT by the application.

### Authentication Requirements
1. **Webhook Security:** Bearer token required in `Authorization` header
   - Returns 401 if missing or invalid
   - Token stored in environment variable (`WEBHOOK_SECRET`)
2. **Google Calendar:** Service Account authentication via `credentials.json`
   - Silent server-to-server auth (no OAuth consent screens)
   - File must be gitignored

### Voice Platform Integration (Vapi)

**Tool Call Payload Structure:**
```json
{
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
            "title": "Interview Prep"
          }
        }
      }
    ]
  }
}
```

**Required Fields in `arguments`:**
- `name`: Attendee name (string)
- `date`: ISO 8601 date `YYYY-MM-DD` (string)
- `time`: 24-hour time `HH:MM` (string)
- `title`: Optional meeting title (string)

### Async Patterns & Latency Safety
- All webhook endpoints must be `async def`.
- Wrap synchronous Google API calls in `asyncio.to_thread()` to prevent blocking.
- **Strict Latency Gate:** External API calls MUST include a timeout (default 8s). Voice providers drop calls if webhooks take too long; failing fast with a "retry" message is better than a hung connection.

### Timezone & Data Integrity
- **UTC Enforcement:** All date/time strings from Vapi MUST be treated as local to the user's context (usually defined in `SPEC.md`) but stored/sent to Google as explicit **UTC ISO-8601** strings.
- Use Python's `zoneinfo` module for all conversions. Never use "naive" datetime objects.

## Build / Lint / Test Commands

Always run before committing:

```bash
# Format code (auto-fixes many issues)
ruff format .

# Check for linting errors
ruff check .

# Type checking with strict mode
mypy . --strict

# Run all tests
pytest

# Run specific test file
pytest tests/test_calendar.py

# Run single test
pytest tests/test_calendar.py::test_create_event_success

# Run with verbose output
pytest -v

# Run tests matching pattern
pytest -k "test_create"
```

## Code Style Guidelines

### Imports

Group imports: stdlib → third-party → local (separate groups with blank lines). Sort alphabetically within groups. Use absolute imports.

```python
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from core.config import Settings
from services.calendar import CalendarService
```

### Type Hints

- **Every** function parameter and return type must be annotated
- Use `Optional[T]` instead of `T | None` for compatibility
- Use `list[T]` instead of `List[T]` (Python 3.9+)
- Explicit return type `-> None` for functions with no return
- Pydantic models for all request/response payloads

```python
def parse_datetime(date_str: str, time_str: str) -> datetime:
    ...

async def create_event(
    service: CalendarService,
    event_data: EventCreate,
) -> EventResponse:
    ...
```

### Naming Conventions

- **Files:** `snake_case.py` (e.g., `calendar_service.py`)
- **Classes:** `PascalCase` (e.g., `CalendarService`)
- **Functions/Methods:** `snake_case` (e.g., `create_event`)
- **Variables:** `snake_case` (e.g., `calendar_id`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_ATTEMPTS`)
- **Private methods:** `_leading_underscore` (e.g., `_parse_credentials`)
- **Test functions:** `test_` prefix (e.g., `test_create_event_success`)

### Formatting

- 4 spaces for indentation
- 88 character line length (Ruff default)
- Double quotes for strings
- Trailing commas in multi-line collections
- One blank line between class methods
- Two blank lines between top-level functions/classes

### Error Handling

Catch specific exceptions, never bare `except:`. Log errors with context. Return safe error messages to voice agents (no stack traces).

```python
import logging

logger = logging.getLogger(__name__)

try:
    result = await service.create_event(data)
except HttpError as e:
    logger.error(f"Calendar API error: {e}")
    raise HTTPException(status_code=500, detail="Failed to create calendar event")
```

### Async Patterns

- All webhook endpoints must be `async def`
- Wrap synchronous Google API calls in `asyncio.to_thread()` to prevent blocking the event loop
- Voice providers drop calls if webhooks take too long

```python
async def create_calendar_event(self, data: EventData) -> dict:
    return await asyncio.to_thread(self._sync_create_event, data)
```

## File Organization

```
.
├── main.py              # FastAPI app, routes, exception handlers
├── schemas.py           # Pydantic models for Vapi payloads
├── core/
│   └── config.py        # Settings, environment variables
├── services/
│   └── calendar.py      # Google Calendar API logic
├── tests/
│   ├── test_main.py     # Route tests (include Vapi payload tests)
│   └── test_calendar.py # Service tests
├── requirements.txt     # Dependencies
├── .env                 # Environment variables (gitignored)
└── credentials.json     # Google Service Account (gitignored)
```

## Testing Requirements

Write tests concurrently with code. Mock all external API calls.

### Required Test Coverage

1. **Authentication:**
   - Missing Bearer token returns 401
   - Invalid Bearer token returns 401
   - Valid token proceeds

2. **Vapi Payload Parsing:**
   - Valid `toolCallList` structure
   - Missing/empty `toolCallList`
   - Missing required fields (`name`, `date`, `time`)
   - Invalid date/time formats
   - Optional `title` field handling

3. **Google Calendar Integration:**
   - Successful event creation
   - Google API errors (mocked HttpError)
   - Invalid calendar ID
   - Authentication failures

4. **Response Format:**
   - Correct Vapi response structure with `toolCallId`
   - User-friendly success messages
   - Graceful error messages for voice agent

### Example Test Structure

```python
@pytest.mark.asyncio
async def test_create_event_success(client, mock_calendar):
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
                            "title": "Interview"
                        }
                    }
                }
            ]
        }
    }
    response = await client.post(
        "/create-event",
        json=payload,
        headers={"Authorization": "Bearer test-token"}
    )
    assert response.status_code == 200
    result = response.json()
    assert "results" in result
    assert result["results"][0]["toolCallId"] == "toolu_123"
```

Minimum 80% code coverage required.

## Security Checklist

- [ ] Bearer token validation on all webhook endpoints
- [ ] Secrets stored in `.env` (never commit)
- [ ] `credentials.json` gitignored
- [ ] No hardcoded secrets in source code
- [ ] Safe error messages (no stack traces to voice agents)
- [ ] Service Account for Google API (not OAuth user flow)

## Pre-commit Checklist

Before completing any task:

1. [ ] Code formatted: `ruff format .`
2. [ ] Linting passes: `ruff check .`
3. [ ] Type checks pass: `mypy . --strict`
4. [ ] All tests pass: `pytest`
5. [ ] Tests written for new features (especially Vapi payload edge cases)
6. [ ] No hardcoded secrets
7. [ ] Error handling includes logging
8. [ ] `credentials.json` in `.gitignore`
9. [ ] `.env` in `.gitignore`

## Deployment Quick Reference

```bash
# Start FastAPI locally
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Expose via Tailscale Funnel
tailscale funnel 8000

# Verify webhook is accessible
curl -H "Authorization: Bearer $WEBHOOK_SECRET" \
     -H "Content-Type: application/json" \
     -X POST https://your-funnel-url/create-event \
     -d '{"message": {"toolCallList": [...]}}'
```

See `SPEC.md` for full assignment requirements and acceptance criteria.
