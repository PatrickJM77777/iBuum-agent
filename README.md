# iBuum Agent 0.1

## 1. What this is

iBuum Agent 0.1 is a small, independent backend service — the first
"digital worker" of the iBuum ecosystem. It exposes a single deterministic
API that turns a minimal training context (age, fatigue, recent session,
etc.) into a structured, machine-readable training recommendation.

It is **not** a chatbot, not an LLM, and not an intelligent coach. It is a
simple rules engine behind a FastAPI endpoint, designed to prove one thing:
that Base44 can call an external iBuum worker and get back structured JSON
it can render however it wants.

## 2. Architecture

```
Base44 (application / orchestration layer)
   │  server-side HTTP request
   ▼
iBuum Agent 0.1 (this project — independent FastAPI service)
   │
   ▼
Rules Engine (app/services/training_rules.py)
   │
   ▼
Structured JSON response
   │
   ▼
Base44 (decides how to display it to the user)
```

Key principles:

- **Independent from Base44.** No shared code, database, or UI.
- **Stateless.** No database, no persisted request logs.
- **API-first, versioned.** `/api/v1/...`.
- **Deterministic.** No AI/LLM calls. Same input → same output.

### Project structure

```
ibuum-agent/
│
├── app/
│   ├── main.py                     # FastAPI app, health check, router wiring
│   ├── api/
│   │   └── routes/
│   │       └── training.py         # HTTP route: validate → auth → call rules → return
│   ├── models/
│   │   ├── training_request.py     # Input schema (Pydantic), data minimization
│   │   └── training_response.py    # Output schema + centralized reason codes
│   ├── services/
│   │   └── training_rules.py       # ALL business logic lives here
│   ├── core/
│   │   ├── config.py                # Env var loading (IBUUM_API_KEY, etc.)
│   │   └── security.py              # X-API-Key header verification
│   └── utils/                       # Reserved for future shared helpers
│
├── tests/
│   └── test_training_endpoint.py   # pytest suite (10 scenarios)
│
├── .env.example
├── requirements.txt
├── README.md
└── .gitignore
```

## 3. Installation

Requires Python 3.12+.

```bash
git clone <this-repo-url> ibuum-agent
cd ibuum-agent
```

## 4. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate      # on Windows: .venv\Scripts\activate
```

## 5. Install requirements

```bash
pip install -r requirements.txt
```

## 6. Configure your `.env`

```bash
cp .env.example .env
```

Edit `.env` and set a real, secure value:

```
IBUUM_API_KEY=replace_with_secure_key
```

The service will refuse to start if `IBUUM_API_KEY` is not set.

## 7. Run the API locally

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

## 8. Access Swagger / interactive docs

```
http://localhost:8000/docs
```

(ReDoc is also available at `http://localhost:8000/redoc`.)

## 9. Call the endpoint with curl

```bash
curl -X POST http://localhost:8000/api/v1/training/recommendation \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace_with_secure_key" \
  -d '{
    "user_id": "anon_8f3a1c",
    "age": 29,
    "sex": "female",
    "height_cm": 167,
    "weight_kg": 61,
    "goal": "general_fitness",
    "training_level": "intermediate",
    "training_days_per_week": 4,
    "fatigue_level": 3,
    "last_session_type": "upper_body",
    "hours_since_last_session": 30,
    "cycle_context": {
      "phase": "luteal",
      "discomfort": "mild"
    }
  }'
```

## 10. Example request body

```json
{
  "user_id": "anon_8f3a1c",
  "age": 29,
  "sex": "female",
  "height_cm": 167,
  "weight_kg": 61,
  "goal": "general_fitness",
  "training_level": "intermediate",
  "training_days_per_week": 4,
  "fatigue_level": 3,
  "last_session_type": "upper_body",
  "hours_since_last_session": 30,
  "cycle_context": {
    "phase": "luteal",
    "discomfort": "mild"
  }
}
```

## 11. Example response

```json
{
  "action": "train",
  "recommended_session": "lower_body",
  "intensity": "moderate",
  "duration_minutes": 45,
  "reason_codes": ["MODERATE_FATIGUE", "RECOVERY_WINDOW_OK"],
  "needs_more_data": false,
  "agent_version": "0.1"
}
```

## 12. How Base44 could later consume this API (integration contract only)

This describes the *expected* contract. Base44 integration itself is not
implemented in this version.

- Base44's backend (not the client/browser) sends a server-side `POST`
  request to `https://<ibuum-agent-host>/api/v1/training/recommendation`.
- The request includes header `X-API-Key: <shared secret>`.
- Base44 sends only the minimal fields defined in
  `app/models/training_request.py` — no names, emails, or medical data.
- Base44 receives the structured JSON response and decides how to phrase
  and display it to the end user.
- Health checks (e.g. uptime monitoring, load balancer probes) can poll
  `GET /health`, which requires no authentication.

## Audit & hardening notes (this revision)

This revision is an **audit and hardening pass only** — no product behavior,
API contract, endpoint, header, or environment variable name was changed.
See the accompanying audit report for full detail. Summary of code changes:

- `app/core/security.py`: the API key comparison now uses
  `secrets.compare_digest()` instead of `==`, to avoid a timing side
  channel. The header name, and 401-on-mismatch behavior, are unchanged.
- `app/main.py`: added a generic exception handler so an unexpected
  internal error always returns a plain `{"detail": "Internal server
  error."}` with status 500, never a stack trace or exception message.
  Only the exception type and request path are logged server-side; the
  request body is never logged.
- `tests/test_training_endpoint.py`: expanded from ~10 to 43 tests,
  covering authentication, input validation boundaries, invalid enums,
  missing fields, malformed JSON, every documented rule-engine scenario,
  and rule-engine invariants (e.g. a `rest` action can never carry an
  active intensity).

## Running the tests

```bash
pytest -v
```

The suite covers: health check, missing/invalid/valid API key, high
fatigue → rest, beginner intensity cap, recent lower-body session
avoidance, female users with and without `cycle_context`, and high
menstrual discomfort handling.

## Assumptions made in this version

1. **Session rotation heuristic.** With no history/database, the baseline
   session recommendation lightly rotates away from `last_session_type`
   (e.g. after upper body, suggest lower body) when no other rule
   overrides it. This is a simple heuristic, not a training program.
2. **Fatigue tiers.** Fatigue 5 → rest; fatigue 4 → reduced intensity/
   duration; fatigue 3 → flagged as `MODERATE_FATIGUE` but otherwise
   normal; fatigue 1–2 → flagged as `LOW_FATIGUE`.
3. **Rule 3 applied symmetrically.** The spec explicitly requested avoiding
   a repeated *lower-body* session within 24h. The same logic was applied
   symmetrically to `upper_body`, since `RECENT_UPPER_BODY_SESSION` was
   already listed as an available reason code.
4. **`needs_more_data` / `INSUFFICIENT_DATA`.** Used when a demanding
   `last_session_type` is known but `hours_since_last_session` is missing,
   so the recovery window can't be confirmed. The service still returns a
   conservative recommendation rather than blocking with
   `request_more_data`, since the required input fields are already
   validated by the schema.
5. **Rule 5 behavior.** High menstrual discomfort sets `action=recovery`,
   `recommended_session=mobility`, `intensity=low`, and caps duration —
   as an *allowed* adjustment, not a forced or generic rule tied to
   menstruation alone (per the "do not assume menstruation means train
   less" instruction).
6. **API key check happens before Pydantic validation errors** are
   surfaced to the caller in terms of dependency order, but FastAPI runs
   route dependencies before the body is parsed in this setup, so an
   invalid key returns 401 even with a malformed body.
7. **`.env` loading** uses `python-dotenv`; in real deployments, real
   environment variables should be set directly and `.env` is not needed
   or committed.
