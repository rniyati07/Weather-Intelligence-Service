# Weather Intelligence

A conversational travel-intelligence assistant that turns raw weather forecasts into grounded trip decisions.

## What it does

Weather Intelligence lets a user describe a trip in plain language — *"I'm planning a 4-day trip to Goa from September 15 to September 18, I love beaches and photography"* — and responds with a decision, not just a forecast: which day is best, what to watch out for, what real places fit the trip, and what to pack. The conversation continues naturally ("What if it rains?", "Keep it relaxed, I'm travelling with my parents.") without the user repeating themselves, and the trip's structured intelligence stays visible alongside the conversation as it evolves.

Every score, risk level, and place shown in the UI is computed by a deterministic backend engine or retrieved from a real external source — the LLM explains, it never invents.

## Core features

- Natural-language trip planning: destination, dates, interests, travel style, and pace extracted from free text
- Deterministic weather intelligence: suitability score, risk level, confidence, best day, watch-out day, and day-by-day breakdown
- Real place discovery matched to the trip's interests and weather — landmarks, beaches, museums, restaurants and cafes, stays (hotels/guest houses/hostels), and sports facilities, all sourced from OpenStreetMap, never invented
- Weather-derived packing recommendations
- Multi-turn conversation with persistent trip context — follow-ups never require repeating known information
- Persistent conversation history, restorable across sessions and browser refreshes
- A secondary manual entry path (pick a destination and dates directly) for users who prefer a form

## Architecture / workflow

```
User message
  → Frontend (React)
  → FastAPI backend
  → LLM extraction (structured intent + trip fields)
  → Geocoding (destination → coordinates)
  → Weather providers (forecast retrieval, with fallback)
  → Deterministic intelligence engine (score, risk, confidence, best/watch-out day)
  → Place discovery (OpenStreetMap / Overpass)
  → LLM response generation (grounded in the data above)
  → Persistence (PostgreSQL)
  → Response
```

One orchestrator, two LLM calls per turn (structured extraction, then response generation) — no agent loop, no autonomous tool-calling. Every fact the LLM narrates was computed or retrieved by the backend first.

## Technology stack

**Backend:** Python 3.11+, FastAPI, SQLAlchemy (async) + Alembic, PostgreSQL, Redis (optional, in-memory cache available for local dev)
**Frontend:** React 19, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router

## Key integrations

| Integration | Purpose |
|---|---|
| **FastAPI** | REST API, request validation, OpenAPI schema |
| **PostgreSQL** | Conversation, message, and trip-context persistence |
| **Groq** (LLM) | Structured trip extraction and conversational response generation |
| **Open-Meteo** | Primary weather forecast provider and geocoding, with OpenWeather / WeatherAPI as configured fallbacks |
| **OpenStreetMap / Overpass** | Real place discovery near the trip destination |

## Repository structure

```
app/
  domain/          Entities, rules, and ports — no framework dependencies
  application/      Use cases (chat orchestration, weather intelligence)
  infrastructure/    Providers, persistence, LLM client, config
  interface/         FastAPI routers, request/response schemas
frontend/
  src/features/      Chat, planner, dashboard, settings UI
  src/services/api/   Typed API client, generated from the OpenAPI spec
migrations/          Alembic database migrations
tests/               Unit, integration, and API contract tests
docs/                Architecture, API contract, and audit documentation
```

## Running the backend locally

```bash
python -m venv .venv
.venv/Scripts/activate          # or: source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env            # fill in real values — see Environment variables below

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Requires a running PostgreSQL instance reachable at `DATABASE_URL`. Set `CACHE_BACKEND=memory` in `.env` to skip Redis for local development.

## Running the frontend locally

```bash
cd frontend
npm install
cp .env.example .env.local      # fill in real values

npm run dev
```

The dev server proxies API requests to the backend and injects the API key server-side — no credentials are ever present in the browser bundle.

## Environment variables

Configured via `.env` (backend) and `frontend/.env.local` (frontend). No secrets are included here — see each project's `.env.example` for the full list.

**Backend** — required: `DATABASE_URL`, `API_KEYS`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`. Optional, with sensible defaults: `OPENWEATHER_API_KEY`, `WEATHERAPI_KEY`, `METEOSTAT_API_KEY` (weather fallback providers), `REDIS_URL`/`CACHE_BACKEND`, `PROVIDER_TIMEOUT_SECONDS`, `RULE_CONFIG_VERSION`, `MAX_FORECAST_HORIZON_DAYS`.

**Frontend** — `VITE_API_BASE_URL`, `VITE_API_TIMEOUT_MS`, plus server-side-only `API_PROXY_TARGET` and `API_KEY` used by the dev proxy (never bundled into client code).

## Testing

```bash
pytest                  # backend — 529 tests (excludes tests/live by default)
ruff check app tests    # lint
mypy app                # type check
lint-imports             # architecture boundary check

cd frontend
npm test                # frontend unit tests (vitest)
npm run typecheck
npm run lint
npm run format:check
npm run build
```

The default backend suite is unit and integration coverage with external providers faked; a small number of integration tests require Docker (Testcontainers) and are skipped otherwise. `tests/live/` (`pytest -m live tests/live`, requires a real `.env`) is a separate, deliberately-excluded suite that hits the real Groq, Open-Meteo, Overpass, and OpenWeather endpoints — see `tests/live/README.md`. Both backend and frontend are gated in CI (`.github/workflows/ci.yml`).

## Known limitations

- **Place discovery depends on a public Overpass endpoint**, which can rate-limit or time out under load; results for a given destination can vary between requests. This is an external reliability constraint, not an application defect. (A second Overpass host once carried as a fallback was removed — it was measured unreachable and never rescued a single request.)
- **`WEATHERAPI_KEY` is not configured** — WeatherAPI is the second (least-priority) forecast fallback; Open-Meteo (primary) and OpenWeather (first fallback) are both live-verified working.
- Full architectural detail and a forensic audit of past system behavior are documented separately in `docs/` (`WEATHER_INTELLIGENCE_FULL_E2E_AUDIT.md`, kept as a historical record — not updated in place). Every issue from that audit's fix list has since been fixed and re-verified live, except Docker/deployment packaging (`docker-compose.yml` and `docker/Dockerfile` exist and are written to spec, but building/running them has not been verified — Docker Desktop was unavailable in the environment that did this work).
