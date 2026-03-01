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

### 1) Private management plane (Tailscale)

The server is managed privately over Tailscale (SSH access is not publicly exposed). This ensures secure operations access without exposing the server to public internet for management.

### 2) Public HTTPS ingress (Caddy)

**Why Caddy instead of Tailscale Funnel:**
- Tailscale Funnel routes through Tailscale's infrastructure, which can be unstable for third-party webhook providers
- Caddy provides a direct, stable public HTTPS endpoint on standard ports (80/443)
- Better compatibility with external webhook services (Vapi, etc.)
- Automatic Let's Encrypt certificate management

Caddy acts as a reverse proxy, terminating TLS on ports 80/443 and forwarding to the local FastAPI port (8000).

### 3) FastAPI binding

Run FastAPI on:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

TLS is terminated by Caddy, not by FastAPI.

---

## Prerequisites

- Python 3.12+
- Google Cloud project with Calendar API enabled
- Google Service Account credentials (`credentials.json`)
- Caddy installed on server (for HTTPS reverse proxy)
- Public hostname or IP with ports 80/443 accessible
- Server firewall allowing inbound HTTP/HTTPS

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
- Set file permissions: `chmod 600 .env credentials.json`

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

## Server deployment (Hetzner VPS with Caddy + Tailscale)

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
# securely place credentials.json (chmod 600)
```

### 3) Start app with systemd

```bash
# Create systemd service
sudo systemctl enable voice-scheduling-agent
sudo systemctl start voice-scheduling-agent
sudo systemctl status voice-scheduling-agent
```

### 4) Configure Caddy reverse proxy

**Why Caddy:** Provides stable public HTTPS endpoint for webhook providers.

Create a Caddyfile (e.g., `/etc/caddy/Caddyfile`):

```
<your-webhook-hostname> {
    encode gzip
    reverse_proxy 127.0.0.1:8000
}
```

Start Caddy:

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
sudo systemctl status caddy
```

### 5) Configure Tailscale (optional, for private management)

If using Tailscale for private SSH access:

```bash
# On server
tailscale up

# From local machine (with tailscale)
ssh icepla@hetzner
```

**Note:** Do NOT use `tailscale funnel` for public ingress — use Caddy instead for stability.

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

## How to Test the Agent

You can test this project in two ways:

### 1) Human Test (Call the Assistant)

- **Preferred (web call):** `<your-vapi-web-call-link-if-available>`
- **Phone call:** `+12408506172` (US number, works internationally)

#### Suggested test script
Say:
- "Appointment tomorrow at 3 with Maria."
- Confirm when asked.

Expected behavior:
1. Assistant greets and collects name/date/time.
2. Assistant confirms details before creating the event.
3. Assistant reports success/failure in natural voice.
4. Event appears in the configured Google Calendar.

> Note: Relative dates like "tomorrow" are resolved by the assistant prompt logic and confirmed before tool call.

---

### 2) Technical Test (Webhook/API)

- **Base URL:** `https://46-225-117-21.sslip.io`
- **Endpoint:** `POST /create-event`
- **Auth:** `Authorization: Bearer <WEBHOOK_SECRET>` (not published in repo)

#### Health check
```bash
curl -i "https://46-225-117-21.sslip.io/healthz"
```
Expected: `200`

#### Auth check (missing token)
```bash
curl -i -X POST "https://46-225-117-21.sslip.io/create-event" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCallList":[{"id":"toolu_1","function":{"name":"unknown_function","arguments":{"foo":"bar"}}}]}}'
```
Expected: `401`

#### Valid create-event call
```bash
curl -s -X POST "https://46-225-117-21.sslip.io/create-event" \
  -H "Authorization: Bearer <WEBHOOK_SECRET>" \
  -H "Content-Type: application/json" \
  -d '{"message":{"toolCallList":[{"id":"toolu_create","function":{"name":"create_calendar_event","arguments":{"name":"Evaluator","date":"2026-03-05","time":"14:00","title":"Submission Verification"}}}]}}'
```
Expected: `200` with `results[0].toolCallId` and success message.

---

## Deployed Links

- **Public webhook endpoint (technical):** `https://46-225-117-21.sslip.io/create-event`
- **Public agent access (human):** `+12408506172` (call to test voice scheduling)

---

## Smoke tests

Set:

```bash
export BASE_URL="https://<your-webhook-url>"
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

### Caddy shows errors or HTTPS not working

Check Caddy status and logs:

```bash
sudo systemctl status caddy
sudo journalctl -u caddy --since "10 minutes ago"
```

Verify ports 80/443 are open in your cloud provider firewall.

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
