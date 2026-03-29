# Ticket Triage Service

An AI-powered support ticket classification API that automatically categorises, prioritises, and routes incoming customer tickets — then persists every decision for audit and review.

---

## Why This Project Matters

Support teams drown in tickets. A single misrouted or deprioritised ticket can cost an enterprise customer their trust — or cause real revenue loss during an outage. Manual triage is slow, inconsistent, and impossible to scale.

This service brings consistency and speed to the first-response layer: every ticket is classified in under a second, a suggested customer reply is generated automatically, and deterministic business rules ensure that critical edge-cases (outages, angry enterprise customers, low-confidence predictions) are always escalated — regardless of what the model says. The result is a shorter time-to-first-response and a clear, auditable trail of every triage decision.

---

## Project Overview

**Ticket Triage Service** is a REST API built with [FastAPI](https://fastapi.tiangolo.com/). It accepts a support ticket payload, sends it to an OpenAI language model for structured classification, overlays a set of deterministic business rules, and returns a rich triage result that routing systems or human agents can act on immediately. Every triage decision is stored in a local SQLite database.

### What it produces for each ticket

| Field | Description |
|---|---|
| `category` | `billing`, `technical_issue`, `account_access`, `bug_report`, `feature_request`, `outage`, `cancellation`, `other` |
| `priority` | `low`, `medium`, `high`, `urgent` |
| `sentiment` | `calm`, `frustrated`, `angry`, `neutral` |
| `recommended_team` | `support`, `billing_ops`, `engineering`, `sre_ops`, `account_management` |
| `short_summary` | ≤ 200-character factual summary |
| `suggested_reply` | ≤ 600-character customer-safe draft reply |
| `confidence` | `0.0 – 1.0` model confidence score |
| `needs_escalation` | `true` / `false` escalation flag |

---

## Architecture

```
Client
  │
  ▼
┌─────────────────────────────────────────────────┐
│  FastAPI  (main.py)                             │
│  POST /triage   GET /health                     │
└───────────────────┬─────────────────────────────┘
                    │ TicketInput
                    ▼
┌─────────────────────────────────────────────────┐
│  Triage Service  (triage_service.py)            │
│                                                 │
│  1. Build user prompt  (prompts.py)             │
│  2. Call OpenAI API → structured JSON output    │
│     (response_schemas.py)                       │
│  3. Parse + validate with Pydantic              │
│     (schemas.py)                                │
│  4. Fallback result on any failure              │
└───────────────────┬─────────────────────────────┘
                    │ model result
                    ▼
┌─────────────────────────────────────────────────┐
│  Business Rules  (rules.py)                     │
│                                                 │
│  • Outage category  → force escalation          │
│  • "production down" in title → urgent          │
│  • Enterprise + angry + high → escalate         │
│  • Confidence < 0.65 → escalate                 │
└───────────────────┬─────────────────────────────┘
                    │ final result
                    ▼
┌─────────────────────────────────────────────────┐
│  SQLite Database  (database.py)                 │
│  triage_results table — stores model result     │
│  and final result side-by-side for audit        │
└─────────────────────────────────────────────────┘
```

### Key files

```
app/
  main.py             # FastAPI app, endpoints, error handlers
  triage_service.py   # OpenAI call, JSON parsing, fallback logic
  rules.py            # Deterministic post-model business rules
  schemas.py          # Pydantic input/output models and enums
  prompts.py          # System prompt for the AI model
  response_schemas.py # JSON schema for structured model output
  database.py         # SQLite init and persistence helpers
  logging_config.py   # Structured JSON logging setup
data/
  sample_tickets.json # 20 example tickets for manual testing
tests/                # pytest test suite
```

---

## Setup

### Prerequisites

- Python 3.11+
- An [OpenAI API key](https://platform.openai.com/account/api-keys)

### 1. Clone and install dependencies

```bash
git clone https://github.com/dianzi1000/ticket_triage.git
cd ticket_triage
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=sk-...
# Optional: override the default SQLite path
# TRIAGE_DB_PATH=triage.db
```

### 3. Start the server

```bash
uvicorn app.main:app --reload
```

The API is now available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

### 4. Run the tests

```bash
pytest tests/
```

---

## Example Request / Response

### POST `/triage`

**Request**

```bash
curl -X POST http://localhost:8000/triage \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Production system is completely down",
    "description": "Our entire production environment stopped responding at 14:32 UTC. All API calls are returning 503 errors. This is affecting 10,000+ end users and causing revenue loss every minute.",
    "customer_tier": "enterprise",
    "product_name": "Core Platform"
  }'
```

**Response** `200 OK`

```json
{
  "category": "outage",
  "priority": "urgent",
  "sentiment": "frustrated",
  "recommended_team": "sre_ops",
  "short_summary": "Enterprise customer reports full production outage since 14:32 UTC; all API calls returning 503, 10k+ users affected.",
  "suggested_reply": "Thank you for reaching out. We have identified this as a critical production outage and have escalated it to our on-call SRE team immediately. We will provide a status update within 15 minutes.",
  "confidence": 0.97,
  "needs_escalation": true
}
```

### GET `/health`

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

### Validation error `422`

Sending a ticket with a title shorter than 3 characters returns:

```json
{
  "detail": "Invalid ticket input",
  "errors": [
    {
      "field": "body -> title",
      "message": "String should have at least 3 characters"
    }
  ]
}
```

---

## Limitations

- **OpenAI dependency** — the service requires a live OpenAI API key. If the API is unavailable or times out (30 s limit), a safe fallback result is returned with `confidence: 0.0` and `needs_escalation: false`.
- **No authentication** — the `/triage` endpoint is unauthenticated. It should sit behind an API gateway or internal network boundary in production.
- **SQLite storage** — suitable for development and low-volume deployments. Not designed for concurrent write-heavy workloads or horizontal scaling.
- **Single model, single prompt** — all ticket types are handled by one prompt. Edge-case categories (e.g. legal, GDPR requests) may be mis-classified as `other`.
- **No retry logic** — transient OpenAI errors produce an immediate fallback; there is no exponential back-off or retry queue.
- **English-only** — the system prompt and validation are tuned for English-language tickets; other languages may yield lower-confidence results.

---

## Future Improvements

- **Authentication & rate limiting** — add API key auth and per-client rate limiting at the gateway layer.
- **Async endpoint** — switch the `/triage` handler to `async def` and use the async OpenAI client to support higher request concurrency.
- **Retry / circuit breaker** — add exponential back-off on transient API errors and a circuit breaker to shed load gracefully.
- **Swap SQLite for Postgres** — adopt SQLAlchemy with a Postgres backend to support concurrent writes and horizontal scaling.
- **Feedback loop / fine-tuning** — expose a `PATCH /triage/{id}/feedback` endpoint so agents can correct labels, then periodically fine-tune a smaller model on the accumulated corrections.
- **Streaming replies** — stream the `suggested_reply` field back to the client for faster perceived response times.
- **Multi-language support** — add language detection and language-specific prompts or a translation step.
- **Admin dashboard** — a simple read-only UI over the `triage_results` table for team leads to monitor volume, category distribution, and escalation rates.
- **Configurable business rules** — move rules from hard-coded Python into a database-backed rule engine so non-engineers can tune them without a deployment.
