# Voice Scheduling Agent - Specification

## Assignment Overview

Build and deploy a real-time voice assistant that collects meeting details from users and creates actual calendar events.

**Deadline:** Monday, March 2nd, 2026

## Core Requirements

### User Conversation Flow
The voice agent must:
1. **Initiate** conversation with a greeting
2. **Collect** required information:
   - Name (required)
   - Preferred date and time (required)
   - Meeting title (optional)
3. **Confirm** all details with the user before proceeding
4. **Create** a real calendar event via webhook
5. **Inform** user of success or failure

### Technical Stack
- **Voice Platform:** Vapi (recommended) or Retell
- **Backend:** Python 3.12+ with FastAPI
- **Hosting:** Hetzner Linux VPS
- **Networking:** Tailscale Funnel (public HTTPS endpoint → local port)
- **Calendar:** Google Calendar API via Service Account
- **LLM:** Any provider of choice

### Infrastructure Constraints
| Component | Constraint |
|-----------|------------|
| TLS/HTTPS | Handled by Tailscale Funnel, NOT by FastAPI |
| Auth | Bearer token in `Authorization` header mandatory |
| Google Auth | Service Account with `credentials.json` (silent, no OAuth flow) |
| Cost | Minimize using free tiers and existing VPS only |

## Webhook Specification

### Endpoint
```
POST /create-event
Authorization: Bearer <WEBHOOK_SECRET>
Content-Type: application/json
```

### Request Payload (Vapi ToolCall Schema)

**Required Headers:**
- `Authorization: Bearer <token>` — returns 401 if missing or invalid

**Request Body:**
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

**Field Requirements:**
| Field | Required | Format | Description |
|-------|----------|--------|-------------|
| `name` | Yes | String | Attendee/participant name |
| `date` | Yes | ISO 8601 Date (`YYYY-MM-DD`) | Event date |
| `time` | Yes | 24-hour Time (`HH:MM`) | Event start time |
| `title` | No | String | Meeting title (use default if omitted) |

**Response Format:**
```json
{
  "results": [
    {
      "toolCallId": "toolu_123",
      "result": "Calendar event 'Interview Prep' created for John Doe on March 5, 2026 at 2:00 PM"
    }
  ]
}
```

Error responses should return user-friendly messages the voice agent can speak aloud.

## Submission Requirements

### Deliverables Checklist
- [x] GitHub repository with complete source code
- [x] README.md containing:
  - [x] Deployed agent URL or public link
  - [x] Instructions on how to test the agent
  - [x] Optional: Local development setup guide
  - [x] Explanation of calendar integration approach
- [x] Proof of successful event creation:
  - [x] Screenshots/logs, OR
  - [x] Short Loom video (recommended)

### Code Quality Standards
Before submission, verified:
- [x] All code formatted with `ruff format .`
- [x] Linting passes with `ruff check .`
- [x] Type checking passes with `mypy . --strict`
- [x] All tests pass with `pytest` (61 passed)
- [x] No secrets committed (use `.env` and `.gitignore`)

## Acceptance Criteria

The assignment is complete when:
1. [x] Voice agent is publicly accessible and can be called
2. [x] Agent successfully collects name, date, and time from caller
3. [x] Agent confirms details before creating event
4. [x] Real calendar event appears in Google Calendar
5. [x] User receives verbal confirmation of success/failure
6. [x] Code is documented and follows repository guidelines

## Questions?

Contact: Lysann Briggs (vikara.ai)
