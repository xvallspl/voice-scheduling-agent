# Voice Scheduling Agent

A production-ready FastAPI webhook server that receives Vapi tool calls and creates Google Calendar events with strict authentication, validation, and voice-friendly responses.

## What this service does

This backend powers a voice scheduling flow:

1. Voice assistant collects:
   - `name` (required)
   - `date` (required, `YYYY-MM-DD`)
   - `time` (required, `HH:MM`)
   - `title` (optional)
2. Voice platform sends a webhook call to `POST /create-event`
3. Server validates auth and payload
4. Server creates an event in Google Calendar
5. Server returns a Vapi-compatible `results[]` response with `toolCallId`

---

## Architecture

```text
.
├── main.py
├── core/
│   ├── config.py      # typed settings (Pydantic Settings)
│   ├── security.py    # Bearer auth dependency
│   └── logging.py     # structured/idempotent logging
├── routers/
│   └── create_event.py
├── schemas/
│   ├── vapi.py
│   └── calendar.py
├── services/
│   └── calendar.py    # async-safe Google Calendar adapter
└── tests/
    ├── test_auth.py
    ├── test_schemas.py
    ├── test_calendar.py
    └── test_router.py
```

Design boundaries:

- **Routers**: orchestration only
- **Services**: external integration/business logic
- **Schemas**: API contract validation
- **Core**: config/auth/logging utilities

---

## Infrastructure model (important)

### 1) Tailscale (private management plane)

The server is managed privately over a Tailscale tailnet (SSH access is not publicly exposed).

### 2) Tailscale Funnel (public HTTPS ingress)

Funnel publishes a public HTTPS URL and forwards requests to your local FastAPI port (8000).

### 3) FastAPI binding

For this deployment model, run FastAPI on:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

TLS is terminated by Funnel, not by FastAPI.

---

## Prerequisites

- Python 3.12+
- Google Cloud project with Calendar API enabled
- Google Service Account credentials (`credentials.json`)
- Tailscale installed + authenticated on server
- Funnel URL from `tailscale funnel status`

---

## Environment variables

Use `.env.example` as template.

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEBHOOK_SECRET` | Yes | - | Bearer token for webhook auth (min 24 chars) |
| `GOOGLE_CALENDAR_ID` | No | `primary` | Target calendar ID |
| `GOOGLE_CREDENTIALS_PATH` | No | `credentials.json` | Service account JSON path |
| `TIMEZONE` | No | `UTC` | Local interpretation timezone for incoming date/time |
| `DEFAULT_EVENT_DURATION_MINUTES` | No | `60` | Event duration |
| `DEFAULT_EVENT_TITLE` | No | `Meeting` | Fallback title |
| `LOG_LEVEL` | No | `INFO` | Logging level |

Security:
- Never commit `.env`
- Never commit real `credentials.json`

---

## Timezone & Data Integrity

Incoming `date` + `time` from voice payloads are interpreted as **local time in `TIMEZONE`**, then converted to **explicit UTC ISO-8601** before sending to Google Calendar.

- Input example: `date=2026-03-05`, `time=14:00`, `TIMEZONE=America/New_York`
- Converted/stored/sent example: `2026-03-05T19:00:00+00:00` (UTC)

This prevents ambiguity and ensures consistent calendar storage/behavior.

---

## Local development

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env
# place credentials.json (gitignored)
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl -i http://localhost:8000/healthz
```

---

## Server deployment (Hetzner + Tailscale Funnel)

### 1) Bootstrap server (first time)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
```

### 2) Deploy app

```bash
mkdir -p ~/apps
cd ~/apps
git clone <REPO_URL> voice-scheduling-agent
cd voice-scheduling-agent

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# edit .env with production values
# securely place credentials.json
```

### 3) Start app

```bash
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4) Expose with Funnel

```bash
tailscale funnel 8000
tailscale funnel status
```

---

## Webhook contract

### Endpoint

```http
POST /create-event
Authorization: Bearer <WEBHOOK_SECRET>
Content-Type: application/json
```

### Request payload

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

### Response payload

```json
{
  "results": [
    {
      "toolCallId": "toolu_123",
      "result": "..."
    }
  ]
}
```

Behavior notes:
- Missing/invalid auth => `401`
- Unknown functions => safe voice-friendly `200` result message
- Malformed/empty tool-call payload => safe voice-friendly `200` result message
- Internal errors are not leaked as stack traces

---

## Smoke tests

Set:

```bash
export BASE_URL="https://<your-funnel-url>"
export WEBHOOK_SECRET="<server-secret>"
```

### M1 auth contract

Health:

```bash
curl -i "${BASE_URL}/healthz"
# expected: 200
```

Missing auth:

```bash
curl -i -X POST "${BASE_URL}/create-event" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCallList":[{"id":"toolu_1","function":{"name":"unknown_function","arguments":{"foo":"bar"}}}]}}'
# expected: 401
```

Invalid auth:

```bash
curl -i -X POST "${BASE_URL}/create-event" \
  -H "Authorization: Bearer invalid_token_12345678901234567890" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCallList":[{"id":"toolu_1","function":{"name":"unknown_function","arguments":{"foo":"bar"}}}]}}'
# expected: 401
```

Valid auth reaches handler:

```bash
curl -i -X POST "${BASE_URL}/create-event" \
  -H "Authorization: Bearer ${WEBHOOK_SECRET}" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCallList":[{"id":"toolu_1","function":{"name":"unknown_function","arguments":{"foo":"bar"}}}]}}'
# expected: 200 and results[0].toolCallId == "toolu_1"
```

---

## Quality gates

Run before commit:

```bash
ruff format .
ruff check .
mypy . --strict
pytest
```

---

## Troubleshooting

### `ssh hetzner` fails with fish `Unsupported use of '='`
Use bash login explicitly:

```bash
ssh -t hetzner /bin/bash -l
```

### Funnel shows `No serve config`

```bash
tailscale funnel 8000
tailscale funnel status
```

### Valid token still returns 401
- Confirm server `.env` has correct `WEBHOOK_SECRET`
- Confirm request header is exactly `Authorization: Bearer <token>`
- Restart app after env changes

### Google event creation fails
- Check `credentials.json` exists and is readable
- Ensure service account has access to target calendar
- Verify `GOOGLE_CALENDAR_ID`

---

## Security checklist

- Bearer token validation on webhook route
- No secrets committed (`.env`, `credentials.json` ignored)
- Voice-safe error messages (no stack traces to caller)
- Service Account auth (no OAuth consent flow)
