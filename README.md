# Voice Scheduling Agent

A real-time voice webhook server built with FastAPI that integrates with Vapi voice assistants and Google Calendar to create calendar events from voice conversations.

## Architecture

The application follows strict separation of concerns:

- `routers/` - FastAPI route handlers (orchestration only, no business logic)
- `schemas/` - Pydantic models for request/response validation
- `services/` - Business logic and external API integrations
- `core/` - Configuration, authentication, logging, and shared utilities

**Planned Structure:**

```
.
├── main.py                 # FastAPI app factory
├── core/                   # Core utilities
│   ├── config.py          # Settings management
│   ├── logging.py         # Logging setup
│   └── security.py        # Bearer token auth
├── routers/               # Route handlers
│   └── create_event.py    # /create-event endpoint
├── schemas/               # Pydantic models
│   ├── vapi.py           # Vapi request/response schemas
│   └── calendar.py       # Calendar event schemas
├── services/              # Business logic
│   └── calendar.py       # Google Calendar integration
├── tests/                 # Test suite
│   ├── test_schemas.py   # Schema validation tests
│   ├── test_calendar.py  # Service layer tests
│   └── test_router.py    # Router integration tests
├── .env.example          # Environment template
├── requirements.txt      # Dependencies
└── IMPLEMENTATION_CHECKLIST.md  # Development tracking
```

## Deployment Model

This project is deployment-provider agnostic. The FastAPI webhook can run on any environment capable of hosting Python services (local VM, VPS, cloud instance, or container platform). The only requirements are:

- Python 3.12+
- Network exposure for the webhook endpoint (public URL)
- Bearer token configured for webhook authentication
- Google Calendar API access via Service Account

### Infrastructure Context (This Implementation)

For this assignment, I reused an existing **private server instance** I already maintained. The host is not directly exposed to the public internet, and administrative access is only available through SSH over a Tailscale tailnet.

Because inbound access to the server is sealed, the webhook is exposed publicly using **Tailscale Funnel**. Funnel provides a public HTTPS endpoint and forwards requests to the local FastAPI service port.

**Security Boundary:**
- Management plane: private (tailnet-only SSH)
- Application ingress: public only through Funnel endpoint
- Application-level protection: Bearer token validation on webhook requests

**Why this deployment approach:**
I intentionally kept the application architecture provider-agnostic and separated it from infrastructure specifics. For this submission, I reused an existing private server instance where administrative access is restricted to SSH over Tailscale. To satisfy the public webhook requirement without opening direct inbound ports, I used Tailscale Funnel to expose only the webhook endpoint over HTTPS while keeping the host's management plane private.

## Quick Start

### Prerequisites

- Python 3.12+
- Google Cloud project with Calendar API enabled
- Service Account credentials JSON file

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. **Place Google credentials:**
   ```bash
   # Download from Google Cloud Console and place as credentials.json
   ```

4. **Run the server:**
   Development only: binding to `0.0.0.0` is convenient for local testing.
   For production, bind to localhost and expose through Funnel or a TLS reverse proxy.
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Test the webhook:**
   ```bash
   curl -X POST http://localhost:8000/create-event \
     -H "Authorization: Bearer $WEBHOOK_SECRET" \
     -H "Content-Type: application/json" \
     -d '{
       "message": {
         "toolCallList": [{
           "id": "toolu_123",
           "function": {
             "name": "create_calendar_event",
             "arguments": {
               "name": "John Doe",
               "date": "2026-03-05",
               "time": "14:00",
               "title": "Test Meeting"
             }
           }
         }]
       }
     }'
   ```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WEBHOOK_SECRET` | Yes | - | Bearer token for webhook authentication (minimum 24 chars) |
| `GOOGLE_CALENDAR_ID` | No | `primary` | Calendar ID for event creation |
| `GOOGLE_CREDENTIALS_PATH` | No | `credentials.json` | Path to service account credentials |
| `TIMEZONE` | No | `UTC` | Default timezone for events |
| `DEFAULT_EVENT_DURATION_MINUTES` | No | `60` | Default meeting duration |
| `DEFAULT_EVENT_TITLE` | No | `Meeting` | Default title when none provided |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |

## Production Deployment

### Option 1: Private Server + Tailscale Funnel (Used Here)

For servers with sealed inbound access, use Tailscale Funnel:

```bash
# On the private server
uvicorn main:app --host 127.0.0.1 --port 8000
tailscale funnel 8000
# Public HTTPS URL will be provided by Funnel
```

### Option 2: VPS with Public Interface

For cloud providers or VPS with public networking:

Use HTTPS termination via reverse proxy (for example, Nginx/Caddy) before exposing
the webhook publicly. Do not expose bearer-token endpoints over plain HTTP.

```bash
# Clone and setup
git clone <repo-url>
cd voice-scheduling-agent
pip install -r requirements.txt
cp .env.example .env
# Edit .env with production values

# Start server bound locally behind reverse proxy
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Configure Vapi

- Set webhook URL to your public URL + `/create-event`
- Add Authorization header with your `WEBHOOK_SECRET`

## Testing

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=. --cov-report=term-missing
```

## Quality Gates

Always run before committing:
```bash
ruff format .
ruff check .
mypy . --strict
pytest
```

## Voice Integration

### Vapi Payload Schema

The webhook expects this exact format:

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

Response format:
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

## License

MIT
