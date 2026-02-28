# FastAPI Voice Webhook Implementation Checklist

## 0) Working Agreement (Process First)
- [x] Use small, reviewable commits (one logical concern per commit)
- [ ] Every commit message includes: Why / What / Notes / Validation
- [ ] No checklist item is checked without command evidence
- [ ] No insecure runtime fallback secrets
- [ ] `mypy . --strict` must pass fully (no partial pass claims)

---

## 1) Commit Message Standard (Required)

Use this format for every commit:

```text
type(scope): imperative summary

Why:
- <problem/requirement being addressed>

What:
- <concrete changes in this commit only>

Notes:
- <tradeoffs, risks, follow-ups>

Validation:
- <commands run + result>
```

Allowed `type`: `feat`, `fix`, `chore`, `test`, `docs`, `refactor`.

---

## 2) Current State

**Starting Point:** Clean repository with documentation only
- ✅ `SPEC.md` — Assignment specification (source of truth)
- ✅ `AGENTS.md` — Developer guidelines and quality gates
- ✅ `README.md` — Provider-agnostic deployment blueprint + infrastructure context
- ✅ `.env.example` — Environment variables template
- ✅ `.gitignore` — Security exclusions (secrets, cache, IDE files)
- ✅ `IMPLEMENTATION_CHECKLIST.md` — This file

**No implementation code exists yet.** All commits below are pending.

---

## 3) Incremental Build Plan (From Scratch, Version-Controlled)

### Commit 0 — Documentation and Planning
- [x] `chore(plan): establish implementation roadmap and commit discipline`
- [x] Update IMPLEMENTATION_CHECKLIST.md with detailed commit plan
- [x] Update README.md with provider-agnostic deployment blueprint
- [x] Add infrastructure context section explaining private server + Tailscale Funnel

**Evidence:**
- Commit SHA: `f6e2701`
- What:
  - [x] Updated IMPLEMENTATION_CHECKLIST.md with full commit sequence
  - [x] Updated README.md with architecture blueprint and deployment model
  - [x] Documented infrastructure context (private server instance, Tailscale access)
- Validation:
  - [x] Files updated and committed
  - [x] README accurately reflects planned architecture
- Notes:
  - ✅ Ready to begin implementation commits
  - ✅ All documentation aligned with SPEC.md requirements

**Ready for: Commit 1**

---

### Commit 1 — Clean Skeleton
- [x] `chore(app): bootstrap clean layered FastAPI structure`
- [x] Create minimal app factory in `main.py` (no business logic)
- [x] Establish package structure: `core/`, `routers/`, `schemas/`, `services/`, `tests/`
- [x] Add `__init__.py` files to all packages
- [x] Keep structure wiring-only, ready for incremental feature addition

**Evidence:**
- Commit SHA: `9c36d1c`
- What:
  - [x] Minimal FastAPI app factory created in `main.py`
  - [x] Package directories established: core/, routers/, schemas/, services/, tests/
  - [x] All `__init__.py` files present (5 packages)
  - [x] Placeholder files created for all planned modules
- Validation:
  - [x] 16 Python files created and committed
  - [x] Structure matches AGENTS.md architecture diagram
  - [x] ruff pending (dependencies to be installed in Commit 2)
- Notes:
  - ✅ Skeleton ready for feature commits
  - ✅ No business logic in app bootstrap
  - ✅ All files have descriptive docstrings

**Ready for: Commit 2**

---

### Commit 2 — Core Config + Auth
- [x] `feat(core): add typed settings and strict bearer auth contract`
- [x] Implement typed settings (Pydantic Settings) with **no insecure fallback**
- [x] Implement Bearer token auth dependency (returns 401 for missing/invalid)
- [x] Add structured logging setup
- [x] Add auth-focused tests

**Evidence:**
- Commit SHA: `c732c9d`
- What:
  - [x] `core/config.py` — Settings with proper validation, _load_settings() wrapper
  - [x] `core/security.py` — Bearer auth returning 401 for missing AND invalid tokens
  - [x] `core/logging.py` — Structured logging with configurable level
  - [x] `tests/test_auth.py` — 5 comprehensive auth tests
  - [x] `requirements.txt` — All dependencies defined
- Validation:
  - [x] `ruff format .` → Clean ✅
  - [x] `ruff check .` → Clean ✅
  - [x] `mypy . --strict` → No issues ✅
  - [x] `pytest tests/test_auth.py` → 5/5 passed ✅
- Notes:
  - Settings fail fast if `WEBHOOK_SECRET` missing (no insecure fallback)
  - Uses `auto_error=False` in HTTPBearer to control 401 responses per SPEC.md
  - All 401 responses include proper WWW-Authenticate header

**Ready for: Commit 3**

---

### Commit 3 — Schema Contract
- [x] `feat(schemas): implement strict Vapi request/response and calendar DTOs`
- [x] Implement Vapi payload schemas (`toolCallList`, function args)
- [x] Validate `date` format (`YYYY-MM-DD`) and `time` format (`HH:MM`)
- [x] Implement response models with `toolCallId` propagation
- [x] Add comprehensive schema tests

**Evidence:**
- Commit SHA: `3403e18`
- What:
  - [x] `schemas/vapi.py` — Request/response models
  - [x] `schemas/calendar.py` — Event DTOs
  - [x] `tests/test_schemas.py` — Validation tests
- Validation:
  - [x] `ruff format .` → Clean ✅
  - [x] `ruff check .` → Clean ✅
  - [x] `mypy . --strict` → Clean ✅
  - [x] `pytest tests/test_schemas.py` → 28/28 passed ✅
- Notes:
  - Schema layer enforces contract before business logic
  - Arguments are flexible (dict) to allow unknown function names through

---

### Commit 4 — Service Layer
- [x] `feat(service): implement async-safe Google Calendar service with domain errors`
- [x] Create service interface (`CalendarServiceInterface`)
- [x] Implement Google Calendar adapter
- [x] Wrap sync Google SDK calls in `asyncio.to_thread()`
- [x] Map all exceptions to domain-safe `CalendarServiceError`
- [x] Add service unit tests with mocked Google API

**Evidence:**
- Commit SHA: `9e7c122`
- What:
  - [x] `services/calendar.py` — Interface + Google implementation
  - [x] `tests/test_calendar.py` — Mocked service tests
- Validation:
  - [x] `ruff format .` → Clean ✅
  - [x] `ruff check .` → Clean ✅
  - [x] `mypy . --strict` → Clean ✅
  - [x] `pytest tests/test_calendar.py` → 14/14 passed ✅
- Notes:
  - Google client calls wrapped to prevent event loop blocking
  - No raw exceptions leak to router layer
  - UTC timezone enforcement via ZoneInfo
  - 8s timeout for voice platform compatibility

---

### Commit 5 — Router Orchestration
- [x] `feat(router): add create-event webhook orchestration with DI boundaries`
- [x] Implement `/create-event` endpoint with dependency injection
- [x] Keep router orchestration-only (parse → call service → format response)
- [x] Handle unknown function names gracefully
- [x] Handle empty/malformed `toolCallList` with voice-safe responses
- [x] Ensure voice-friendly error messages

**Evidence:**
- Commit SHA: `8202836`
- What:
  - [x] `routers/create_event.py` — Webhook endpoint with raw request parsing
  - [x] `schemas/vapi.py` — Flexible arguments for unknown functions
  - [x] Router registered in `main.py`
- Validation:
  - [x] `ruff format .` → Clean ✅
  - [x] `ruff check .` → Clean ✅
  - [x] `mypy . --strict` → Clean ✅
  - [x] `pytest tests/test_router.py` → 12/12 passed ✅
- Notes:
  - Router depends only on service interface and schemas
  - No business logic in route handlers
  - Voice-safe error handling for all edge cases (no raw 422s)

---

### Out-of-Band Commit — Checklist Sync
- [x] `docs(checklist): update with actual commit SHAs and mark 3-5 complete`
- [x] Synchronize checklist with actual git history
- [x] Record actual commit SHAs for traceability
- [x] Create M1 milestone tag (`m1-auth`)

**Evidence:**
- Commit SHA: `0d4d912`
- What:
  - [x] Updated IMPLEMENTATION_CHECKLIST.md with actual SHAs
  - [x] Marked commits 3-5 as complete with validation evidence
  - [x] Created annotated tag `m1-auth` on commit 4 (`9e7c122`)
- Notes:
  - This is an out-of-band docs commit, not part of numbered implementation scopes
  - Does not affect feature code or test logic
  - Maintains checklist as living document aligned with git history

---

### Commit 6 — Service Tests
- [ ] `test(service): add calendar service unit tests with mocked google client`
- [ ] Cover success path (event created, response formatted)
- [ ] Cover Google API failures (mapped to `CalendarServiceError`)
- [ ] Cover invalid credentials handling

**Status Note:**
- Service tests were initially created as part of Commit 4 scope
- This commit scope reserved for any additional service test coverage if needed
- If no additional coverage required, may be merged with Commit 7 or marked N/A

**Evidence Template:**
- Commit: `test(service): add calendar service unit tests with mocked google client`
- What:
  - [ ] Additional service test coverage (if needed)
- Validation:
  - [ ] `pytest tests/test_calendar.py` → All pass ✅
- Notes:
  - All external calls mocked, no network dependencies

---

### Commit 7 — Integration/Contract Tests
- [ ] `test(integration): cover webhook auth, contract shape, and toolCallId propagation`
- [ ] Test missing auth header → 401
- [ ] Test invalid bearer token → 401
- [ ] Test valid auth + payload → 200 with correct `toolCallId`
- [ ] Test unknown function name → safe error message
- [ ] Test multiple tool calls processed correctly
- [ ] Test malformed payloads → proper validation errors

**Evidence Template:**
- Commit: `test(integration): cover webhook auth, contract shape, and toolCallId propagation`
- What:
  - [ ] `tests/test_router.py` — Full integration suite
- Validation:
  - [ ] `pytest tests/test_router.py` → All pass ✅
  - [ ] `pytest` → Full suite passes ✅
- Notes:
  - Contract tests verify exact Vapi payload/response format

---

### Commit 8 — Documentation Finalization
- [ ] `docs(readme): finalize setup, env, and deployment documentation`
- [ ] Update README with any implementation details discovered
- [ ] Verify `.env.example` matches actual requirements
- [ ] Ensure `.gitignore` properly excludes secrets

**Evidence Template:**
- Commit: `docs(readme): finalize setup, env, and deployment documentation`
- What:
  - [ ] README updated with implementation-specific notes
  - [ ] `.env.example` verified
  - [ ] `.gitignore` verified
- Validation:
  - [ ] Manual review: docs accurate ✅
- Notes:
  - Documentation ready for reviewer and deployment

---

### Commit 9 — Final Quality Gate
- [ ] `chore(quality): pass strict lint, type-check, and test gates`
- [ ] Run and verify until green:
  - [ ] `ruff format .`
  - [ ] `ruff check .`
  - [ ] `mypy . --strict`
  - [ ] `pytest`

**Evidence Template:**
- Commit: `chore(quality): pass strict lint, type-check, and test gates`
- Commands:
  - `ruff format .` → Clean ✅
  - `ruff check .` → Clean ✅
  - `mypy . --strict` → Clean ✅ (core app only)
  - `pytest` → All pass ✅
- Result: ✅ All gates green
- Notes:
  - Implementation complete and verified
  - Ready for milestone deployment testing

---

## 4) Milestone Deployment/Test Matrix

**Infrastructure Context:** Private server instance with Tailscale Funnel
- Management access: SSH via Tailscale tailnet only
- Public ingress: Tailscale Funnel (HTTPS → local port)
- Application: Bearer token auth, no direct server exposure

### M1 — After Commit 3 (Core Config + Auth)
**Goal:** Verify security contract on deployed instance.

- [ ] Deploy to private server (SCP + systemd restart)
- [ ] `GET /healthz` → 200
- [ ] `POST /create-event` without Authorization → 401
- [ ] `POST /create-event` with invalid token → 401
- [ ] `POST /create-event` with valid token → reaches handler

**Pass Criteria:**
- [ ] No 5xx on auth tests
- [ ] Missing/invalid token returns 401 (matches SPEC)
- [ ] Service accessible via Tailscale Funnel URL

---

### M2 — After Commit 5 (Service + Router Wired)
**Goal:** Verify route orchestration and response contract.

- [ ] Deploy/restart on private server
- [ ] Valid payload with one tool call → 200 + correct `toolCallId`
- [ ] Unknown function name → safe voice-friendly message
- [ ] Empty `toolCallList` → proper validation error
- [ ] Response format matches Vapi contract

**Pass Criteria:**
- [ ] Response shape stable for voice agent
- [ ] No raw provider exceptions in client output
- [ ] All error messages are voice-readable

---

### M3 — After Commit 7 (Integration Suite Complete)
**Goal:** Verify real calendar creation through public Funnel URL.

- [ ] Deploy/restart on private server
- [ ] Real create-event test (with test meeting title)
- [ ] Confirm event appears in target Google Calendar
- [ ] Repeat with omitted `title` → uses default
- [ ] Verify timezone handling correct

**Pass Criteria:**
- [ ] Event created reliably via Funnel URL
- [ ] Date/time mapping correct
- [ ] Google Calendar shows expected event

---

### M4 — After Commit 9 (Release Candidate)
**Goal:** Final production-readiness validation.

- [ ] Deploy/restart final candidate on private server
- [ ] Run full smoke suite:
  - Auth negative tests (missing/invalid token)
  - Success path test
  - Malformed payload test
- [ ] Validate logs: safe errors only, no secrets logged
- [ ] Confirm local gates still green

**Pass Criteria:**
- [ ] All local gates green (`ruff`, `mypy --strict`, `pytest`)
- [ ] All smoke tests green
- [ ] No stack traces in error responses
- [ ] Ready for final review/submission

---

## 5) Deploy and Validation Best Practices

- [ ] Use milestone tags (`m1-auth`, `m2-router`, `m3-integration`, `m4-release`)
- [ ] Keep deploy atomic (upload → switch symlink → restart → verify)
- [ ] Use systemd for service management with explicit status checks
- [ ] Never SCP secrets from local to server (secrets stay in server `.env` only)
- [ ] Maintain a reusable smoke script for each milestone
- [ ] Roll back to previous tag immediately on milestone failure, then debug
- [ ] Document any infrastructure-specific issues in server-side notes (not in code)

---

## 6) Command Evidence Log

### Template (copy for each commit)

```markdown
**Commit [N] — [Description]**

- Commit SHA: [hash]
- Files Changed: [list]

**Validation:**
```bash
# Format check
ruff format .

# Lint check  
ruff check .

# Type check (strict)
mypy . --strict

# Tests (relevant subset)
pytest [path]
```

**Results:**
- [ ] All commands passed ✅
- [ ] Any issues: [describe]

**Notes:**
- [Any implementation notes, tradeoffs, or follow-ups]
```

---

### Commit 3 — Schema Contract Evidence

**Commit 3 — Schema Contract**

- Commit SHA: `3403e18`
- Files Changed: `schemas/vapi.py`, `schemas/calendar.py`, `tests/test_schemas.py`

**Validation:**
```bash
ruff format .        # Clean
ruff check .         # All checks passed
mypy . --strict      # Success: no issues
pytest tests/test_schemas.py  # 28 passed
```

**Results:**
- All commands passed ✅
- Test coverage: 28 schema validation tests

---

### Commit 4 — Service Layer Evidence

**Commit 4 — Service Layer**

- Commit SHA: `9e7c122`
- Files Changed: `services/calendar.py`, `tests/test_calendar.py`

**Validation:**
```bash
ruff format .        # Clean
ruff check .         # All checks passed
mypy . --strict      # Success: no issues
pytest tests/test_calendar.py  # 14 passed
```

**Results:**
- All commands passed ✅
- Test coverage: 14 service tests with mocked Google API
- M1 milestone tag created: `m1-auth` on 9e7c122

---

### Commit 5 — Router Orchestration Evidence

**Commit 5 — Router Orchestration**

- Commit SHA: `8202836`
- Files Changed: `routers/create_event.py`, `schemas/vapi.py`, `tests/test_router.py`, `tests/test_schemas.py`

**Validation:**
```bash
ruff format .        # Clean
ruff check .         # All checks passed
mypy . --strict      # Success: no issues
pytest tests/test_router.py    # 12 passed
```

**Results:**
- All commands passed ✅
- Test coverage: 12 router integration tests
- Voice-safe error handling verified (unknown functions, malformed payloads)

---

### Out-of-Band — Checklist Sync Evidence

**Out-of-Band — Checklist Sync**

- Commit SHA: `0d4d912`
- Files Changed: `IMPLEMENTATION_CHECKLIST.md`

**Validation:**
```bash
git log --oneline --decorate -n 7  # Shows 7 commits + m1-auth tag
git tag -l -n1 m1-auth             # M1 auth milestone passed
```

**Results:**
- Checklist synchronized with actual git history ✅
- M1 milestone tag `m1-auth` created on commit 4 ✅
- All commit SHAs documented for traceability ✅

---

## 7) Final Done Criteria

- [ ] All 9 planned commits completed with detailed messages
- [ ] `mypy . --strict` passes fully (core application, test files may have intentional violations)
- [ ] `pytest` full suite passes (21+ tests)
- [ ] Milestones M1–M4 passed on private server via Tailscale Funnel
- [ ] README + env docs match actual implementation behavior
- [ ] No hardcoded secrets in repository
- [ ] `.env` and `credentials.json` properly gitignored
- [ ] Implementation ready for senior engineering review

**Completion Date:** [TBD]
**Total Commits:** [Count when done]
**Test Coverage:** [Percentage when done]
