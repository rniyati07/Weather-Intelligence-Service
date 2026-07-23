# Weather Intelligence Service — Implementation & Development Guide

## 1. Introduction

### 1.1 Purpose
The official handbook for building, configuring, testing, integrating, deploying, and maintaining the Weather Intelligence Service. A developer with repository access should be able to implement the complete system by following §7 in order.

### 1.2 Audience
Backend engineers, AI engineers, frontend engineers integrating the assistant UI, DevOps, and maintainers.

### 1.3 Scope
Implementation only. Architecture, product scope, and the API contract are fixed by the documents in §1.5 and are referenced here, never redefined.

**In scope:** environment setup, repository layout, configuration, provider integration, backend implementation phases, AI narration, database and cache setup, frontend assistant integration, testing, deployment, troubleshooting.

**Not in scope:** product rationale (see PRD), architectural decisions (see Bible/TRD), endpoint and payload definitions (see API Spec).

### 1.4 Development Philosophy
| Principle | Implementation rule |
|---|---|
| Clean Architecture | Dependencies point inward. `domain/` imports nothing from `infrastructure/`. Enforced in CI by `import-linter` (Phase 1). |
| SOLID / modular design | One reason to change per module; providers and the LLM sit behind ports. |
| Configuration over hardcoding | Thresholds, priorities, timeouts, and feature flags are configuration — never literals in business logic. |
| Provider independence | No external provider name ever appears in a weather-data response. |
| Determinism | Engines are pure functions of `(normalized_weather, rule_config)`. No clock, no randomness, no I/O. |
| Testability | The domain test suite runs green with the network unplugged and the LLM disabled. |

### 1.5 Related Documents
| Document | Role in this guide |
|---|---|
| `01_Project_Bible.md` | Canonical architecture and decisions. |
| `02_Product_Requirements_Document.md` | Product scope and requirements. |
| `03_Technical_Design_Document.md` | Component responsibilities, data design, testing strategy. |
| `04_API_&_Data_Contract_Specification.md` | **Binding** endpoint, schema, enum, and error contract. Phase 9 implements it verbatim. |

### 1.6 Implementation notes on stack and scope

Two points where this guide's approved stack and feature set differ from earlier documents. Both are recorded here so the doc set stays internally consistent.

1. **Python/FastAPI supersedes the earlier TypeScript/Node decision.** Bible ADR-007 and TRD ADR-12 selected TypeScript to avoid a "language seam" with a TypeScript consumer platform. That rationale does not survive scrutiny: integration is over **HTTP + OpenAPI**, which is language-agnostic, so no seam exists. FastAPI additionally provides first-class request validation (Pydantic) and generated OpenAPI. **Action required:** mark ADR-007 and ADR-12 as *superseded* in the Bible and TRD; do not leave two live, contradicting stack ADRs.
2. **The frontend is a chat-style assistant, not a conversational agent.** Bible §11 / PRD §11 exclude open-ended conversational AI, and that exclusion stands. Phase 10 implements what Bible §25 permits: a chat-shaped UI whose every turn is `text → extract (location, dates) → deterministic API call → render`. The LLM performs parameter extraction and optional narration only. It never answers freely, never holds multi-turn dialogue state as an agent, and never computes intelligence. Form inputs remain available so the UI is fully usable with the LLM disabled.

---

## 2. Development Environment

### 2.1 Supported operating systems
| OS | Status |
|---|---|
| Linux (Ubuntu 22.04+) | Primary |
| macOS (13+, Intel/Apple Silicon) | Supported |
| Windows 11 via WSL2 | Supported — develop inside WSL2, not native Windows (path/signal differences with Docker and uvicorn reload) |

### 2.2 Required tooling
| Tool | Version | Purpose |
|---|---|---|
| Python | 3.11+ | Runtime (3.11 for performance and typing) |
| pip / venv | bundled | Dependency and environment management |
| PostgreSQL | 15+ | Persistence (via Docker locally) |
| Redis | 7+ | Cache (via Docker locally) |
| Docker + Compose v2 | latest | Local infrastructure and packaging |
| Git | 2.30+ | Version control |
| Postman / HTTPie / curl | any | API verification |
| make | optional | Task shortcuts |

### 2.3 IDE recommendations
VS Code (Python, Pylance, Ruff, Docker extensions) or PyCharm Professional. Configure on save: **Ruff** (lint + format), **mypy** (type check). Set the interpreter to the project `.venv`.

### 2.4 Environment setup
```bash
python3 --version                 # expect 3.11+
docker --version && docker compose version
git --version
```

> **Tip:** never install project dependencies globally. Every command in this guide assumes an activated virtual environment (§6.2).

---

## 3. Repository Structure

```
weather-intelligence-service/
├── app/
│   ├── main.py                     # FastAPI app factory, router registration, lifespan
│   ├── interface/                  # Layer 1 — HTTP boundary
│   │   └── http/
│   │       ├── routers/            # intelligence.py, weather.py, narrative.py, providers.py
│   │       ├── schemas/            # Pydantic request/response models (mirror API Spec §9)
│   │       ├── dependencies.py     # auth (X-API-Key), DI wiring, common query params
│   │       ├── envelope.py         # success/data/metadata/error envelope builders
│   │       └── errors.py           # exception handlers → API Spec §7 error contract
│   ├── application/                # Layer 2 — use cases (orchestration)
│   │   ├── use_cases/              # get_weather_intelligence.py, get_best_days.py,
│   │   │                           # get_packing.py, get_raw_weather.py, generate_narrative.py
│   │   └── dto/                    # internal in/out DTOs (not HTTP schemas)
│   ├── domain/                     # Layer 3 — PURE. No I/O, no framework imports.
│   │   ├── entities/               # weather_intelligence.py, daily.py, risk.py, value objects
│   │   ├── engines/
│   │   │   ├── insight/            # rules.py, risk.py, scoring.py
│   │   │   └── recommendation/     # best_worst.py, packing.py, trip_scores.py
│   │   ├── rules/                  # rule config schema + loader contract + version constant
│   │   └── ports/                  # WeatherProvider, WeatherRepository, CachePort, NarrationPort
│   └── infrastructure/             # Layer 4 — implements domain ports
│       ├── providers/              # base.py, openweather.py, weatherapi.py, open_meteo.py,
│       │                           # meteostat.py, registry.py, normalization.py
│       ├── persistence/            # models.py (SQLAlchemy), repositories.py, session.py
│       ├── cache/                  # redis_cache.py, memory_cache.py
│       ├── ai/                     # llm_client.py, prompts/, narration_service.py, fallback.py
│       ├── config/                 # settings.py (pydantic-settings), rule_config/*.yaml
│       └── observability/          # logging.py (structlog), metrics.py, request_context.py
├── migrations/                     # Alembic versions
├── tests/
│   ├── domain/                     # pure unit tests — no network, no DB
│   ├── integration/                # DB + cache + use cases
│   ├── api/                        # endpoint contract tests
│   ├── providers/                  # adapter normalization tests (recorded fixtures)
│   └── fixtures/                   # provider payload fixtures, golden intelligence files
├── frontend/                       # Assistant UI (Phase 10)
├── docker/                         # Dockerfile, entrypoint
├── docs/                           # 01–05 documents
├── .env.example
├── docker-compose.yml
├── pyproject.toml
├── setup.cfg                       # import-linter contracts
└── README.md
```

### 3.1 Directory responsibilities
| Directory | Responsibility | May import from |
|---|---|---|
| `interface/http` | HTTP concerns only: routing, validation, auth, serialization, error mapping. No business logic. | `application` |
| `application` | Sequence use cases; decide cache-hit vs miss; the **only** caller of the narration port. | `domain` (ports + entities) |
| `domain` | Deterministic business logic and contracts. **Imports nothing from other layers.** | — |
| `infrastructure` | Adapters implementing domain ports: providers, DB, cache, LLM, config, logging. | `domain` (ports only) |

### 3.2 Source organization best practices
1. **One module, one responsibility.** A provider adapter knows one API's dialect and nothing else.
2. **Ports live in `domain/ports`, implementations in `infrastructure`.** Use cases depend on the port type, never the concrete class.
3. **Pydantic models belong to `interface/http/schemas`**, not to the domain. Domain entities are plain dataclasses so they stay framework-free and trivially testable.
4. **No `datetime.now()` inside the domain.** Pass timestamps in; otherwise determinism tests become flaky.
5. **Rule thresholds live in `infrastructure/config/rule_config/*.yaml`**, loaded and versioned — never literals in `engines/`.

---

## 4. Environment Configuration

Configuration is loaded once at startup into a typed `Settings` object (`pydantic-settings`) and injected. No module reads `os.environ` directly.

### 4.1 Variable reference
| Variable | Purpose | Default |
|---|---|---|
| `APP_ENV` | `local` / `staging` / `production` | `local` |
| `APP_HOST`, `APP_PORT` | Bind address | `0.0.0.0`, `8000` |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` |
| `LOG_FORMAT` | `json` (prod) / `console` (local) | `console` |
| `API_KEYS` | Comma-separated consumer keys accepted on `X-API-Key` | — |
| `OPS_API_KEYS` | Keys permitted to call `/providers/health` | — |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/wis` | — |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Connection pool | `10`, `5` |
| `REDIS_URL` | `redis://localhost:6379/0` | — |
| `CACHE_BACKEND` | `redis` / `memory` | `redis` |
| `CACHE_TTL_PROVIDER_SECONDS` | Provider-response TTL | `3600` |
| `CACHE_TTL_INTELLIGENCE_SECONDS` | Computed-intelligence TTL | `10800` |
| `OPENWEATHER_API_KEY` | OpenWeather auth | — |
| `WEATHERAPI_KEY` | WeatherAPI auth | — |
| `METEOSTAT_API_KEY` | Meteostat auth | — |
| `PROVIDER_PRIORITY_FORECAST` | Ordered forecast chain | `open_meteo,openweather,weatherapi` |
| `PROVIDER_PRIORITY_HISTORICAL` | Historical chain | `meteostat` |
| `PROVIDER_TIMEOUT_SECONDS` | Per-call timeout | `5` |
| `PROVIDER_RETRY_ATTEMPTS` | Transient retries (same provider) | `2` |
| `PROVIDER_RETRY_BACKOFF_SECONDS` | Base backoff | `0.3` |
| `PROVIDER_HEALTH_TTL_SECONDS` | Health cache | `60` |
| `NARRATION_ENABLED` | Master feature flag for AI narration | `true` |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` | LLM client config | — |
| `LLM_TIMEOUT_SECONDS` | Hard narration timeout | `8` |
| `LLM_MAX_OUTPUT_TOKENS` | Output cap | `400` |
| `RULE_CONFIG_VERSION` | Active rule set (stamped on computed rows) | `2026.07` |
| `MAX_FORECAST_HORIZON_DAYS` | Validation cap (API Spec §11) | `16` |
| `RATE_LIMIT_PER_MINUTE` | Per-key limit | `60` |

### 4.2 `.env.example`
```dotenv
# ---- Application ----
APP_ENV=local
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
LOG_FORMAT=console

# ---- Auth ----
API_KEYS=dev_key_local
OPS_API_KEYS=dev_ops_key_local
RATE_LIMIT_PER_MINUTE=60

# ---- Database ----
DATABASE_URL=postgresql+asyncpg://wis:wis@localhost:5432/wis
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=5

# ---- Cache ----
REDIS_URL=redis://localhost:6379/0
CACHE_BACKEND=redis
CACHE_TTL_PROVIDER_SECONDS=3600
CACHE_TTL_INTELLIGENCE_SECONDS=10800

# ---- Weather providers ----
OPENWEATHER_API_KEY=
WEATHERAPI_KEY=
METEOSTAT_API_KEY=
PROVIDER_PRIORITY_FORECAST=open_meteo,openweather,weatherapi
PROVIDER_PRIORITY_HISTORICAL=meteostat
PROVIDER_TIMEOUT_SECONDS=5
PROVIDER_RETRY_ATTEMPTS=2
PROVIDER_RETRY_BACKOFF_SECONDS=0.3
PROVIDER_HEALTH_TTL_SECONDS=60

# ---- AI narration (optional) ----
NARRATION_ENABLED=true
LLM_API_KEY=
LLM_MODEL=
LLM_BASE_URL=
LLM_TIMEOUT_SECONDS=8
LLM_MAX_OUTPUT_TOKENS=400

# ---- Domain rules ----
RULE_CONFIG_VERSION=2026.07
MAX_FORECAST_HORIZON_DAYS=16
```

> **Rules:** `.env` is git-ignored; only `.env.example` is committed. Startup **fails fast** if a required variable is missing. Open-Meteo requires no key — the service must start and serve with only `DATABASE_URL`, `REDIS_URL`, and `API_KEYS` set.

---

## 5. External Weather Provider Configuration

All four providers implement one `WeatherProvider` port and are classified by **data class** — `forecast` or `historical`. Selection routes by class first, so a forecast request can never fall back to a historical source.

### 5.1 Provider matrix
| Provider | Class | Base URL | Auth | Key var | Role |
|---|---|---|---|---|---|
| Open-Meteo | forecast | `https://api.open-meteo.com` | none | — | **Primary** |
| OpenWeather | forecast | `https://api.openweathermap.org/data/2.5` | `appid` query param | `OPENWEATHER_API_KEY` | Fallback 1 |
| WeatherAPI | forecast | `http://api.weatherapi.com/v1` | `key` query param | `WEATHERAPI_KEY` | Fallback 2 |
| Meteostat | historical | `https://meteostat.net` | API key header | `METEOSTAT_API_KEY` | Historical/baseline only |

### 5.2 Per-provider implementation notes

**Open-Meteo** — primary because it needs no key and has no per-consumer quota friction. Integration: single forecast request with explicit `daily=` fields and metric units. Normalization: WMO weather codes → `WeatherCondition` enum; data is already metric. Fair-use limits apply; caching is the mitigation.

**OpenWeather** — first fallback. Integration: forecast endpoint with `units=metric`; key as `appid`. Normalization: numeric condition codes → `WeatherCondition`; aggregate sub-daily entries into daily min/max where the plan returns 3-hourly data.

**WeatherAPI** — second fallback. Integration: `/forecast.json` with `days=N`; key as `key`. Normalization: condition codes → `WeatherCondition`; fields are already daily-aggregated.

**Meteostat** — historical only. Integration: daily historical endpoint for baseline comparisons. **Never enters the forecast fallback chain.** Normalization: observations → the same internal reading model, flagged as historical.

Common to all four:
- **Timeout:** `PROVIDER_TIMEOUT_SECONDS` per call, enforced by the shared `httpx.AsyncClient`.
- **Retry:** `PROVIDER_RETRY_ATTEMPTS` on transient errors (connection, timeout, 5xx) with exponential backoff; **never** on 4xx.
- **Fallback role:** on exhaustion of retries, the adapter raises a typed `ProviderError` and the registry advances the chain.
- **Normalization:** every adapter returns `NormalizedReading` objects — never a provider payload — and reports field completeness for confidence scoring.

### 5.3 Provider Registry selection logic
```
select(data_class, exclude=[]):
  chain = priority_list(data_class)            # from PROVIDER_PRIORITY_*
  for provider in chain:
      if provider in exclude: continue
      if not provider.is_configured(): continue    # missing key → skip, don't fail
      if health(provider) == unavailable: continue # cached health, TTL-bounded
      yield provider
```
Fetch calls the chain in order until one succeeds. If all forecast providers fail: serve last-known stored data marked `cacheStatus: "stale"`, `degraded: true`; if none exists, return `503 PROVIDER_UNAVAILABLE`.

> **Provider independence is a hard rule.** Provider identity appears only in logs, the `weather_readings_raw.provider` column, and `GET /providers/health`. It must never reach an intelligence, packing, best-days, or raw-weather response.

---

## 6. Local Development Setup

### 6.1 Clone
```bash
git clone <repository-url> weather-intelligence-service
cd weather-intelligence-service
```

### 6.2 Virtual environment
```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows/WSL2: source .venv/bin/activate
python -m pip install --upgrade pip
```

### 6.3 Dependencies
```bash
pip install -e ".[dev]"            # or: pip install -r requirements-dev.txt
```

### 6.4 Configure environment
```bash
cp .env.example .env
# Minimum to boot: DATABASE_URL, REDIS_URL, API_KEYS.
# Provider keys are optional — Open-Meteo needs none.
```

### 6.5 Start infrastructure
```bash
docker compose up -d postgres redis
docker compose ps
```

### 6.6 Apply migrations
```bash
alembic upgrade head
```

### 6.7 Run the API
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6.8 Verify installation
```bash
# Liveness
curl -s http://localhost:8000/health

# Interactive docs
open http://localhost:8000/docs

# A real intelligence call (Goa; no provider key needed — Open-Meteo)
curl -s -H "X-API-Key: dev_key_local" \
  "http://localhost:8000/api/v1/locations/15.2993,74.1240/intelligence?startDate=2026-08-01&endDate=2026-08-05" | jq .
```

**Installation is verified when:** `/health` returns OK, `/docs` renders, the intelligence call returns `success: true` with a populated `dailyIntelligence` array, and `pytest tests/domain -q` passes **with networking disabled**.

---

## 7. Backend Implementation Roadmap

The centrepiece of this guide. Phases are ordered by dependency: each builds only on what precedes it, and each ends in a verifiable state. **Do not skip ahead** — Phases 3–7 deliberately complete the deterministic core before any AI code exists, which is what keeps the boundary provable.

| Phase | Deliverable | Depends on |
|---|---|---|
| 1 | Project skeleton, layer boundaries enforced | — |
| 2 | Typed configuration, logging | 1 |
| 3 | Database schema, repositories | 2 |
| 4 | Four provider adapters | 2 |
| 5 | Registry, fallback, health | 4 |
| 6 | Normalization engine | 4 |
| 7 | Intelligence engines (deterministic core) | 3, 6 |
| 8 | AI narration (optional layer) | 7 |
| 9 | REST API per contract | 7, 8 |
| 10 | Assistant frontend | 9 |
| 11 | Test suite completion | all |
| 12 | Docker & deployment | all |

---

### Phase 1 — Project Initialization

**Objective.** Create the repository skeleton with the four layers physically separated and the dependency rule mechanically enforced from commit one.

**Overview.** The single most valuable thing this phase produces is not code — it is the `import-linter` contract that makes "domain imports nothing" a build failure rather than a code-review opinion.

**Implementation steps**
1. Initialize the repo, `.gitignore` (`.venv`, `.env`, `__pycache__`, `.pytest_cache`).
2. Create `pyproject.toml` with dependencies and tool config (Ruff, mypy, pytest).
3. Create the full directory tree from §3 with `__init__.py` in every package.
4. Add a minimal `app/main.py` exposing `GET /health`.
5. Configure `import-linter` contracts in `setup.cfg`.
6. Add CI (GitHub Actions) running: `ruff check`, `mypy app`, `lint-imports`, `pytest`.

**Files / modules to create**
`pyproject.toml`, `setup.cfg`, `.gitignore`, `.env.example`, `app/main.py`, full package tree, `.github/workflows/ci.yml`.

**Core dependencies**
```toml
dependencies = [
  "fastapi", "uvicorn[standard]", "pydantic", "pydantic-settings",
  "sqlalchemy[asyncio]", "alembic", "asyncpg",
  "redis", "httpx", "tenacity", "structlog", "pyyaml",
]
[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "pytest-cov", "respx",
       "testcontainers[postgres]", "ruff", "mypy", "import-linter"]
```

**Layer contract (`setup.cfg`)**
```ini
[importlinter]
root_package = app

[importlinter:contract:layers]
name = Clean Architecture layers
type = layers
layers =
    app.interface
    app.application
    app.domain

[importlinter:contract:domain-purity]
name = Domain imports no infrastructure or framework
type = forbidden
source_modules = app.domain
forbidden_modules = app.infrastructure, app.interface, fastapi, sqlalchemy, redis, httpx
```

**Deliverables.** A running skeleton whose architecture rules are enforced by CI.

**Testing / verification**
```bash
uvicorn app.main:app --reload &   # GET /health → 200
lint-imports                      # contracts pass
ruff check . && mypy app && pytest -q
```
Deliberately add `from app.infrastructure import x` inside `app/domain/` and confirm `lint-imports` **fails**. Then remove it. This proves the guardrail works.

**Completion checklist**
- [ ] Tree matches §3; every package has `__init__.py`
- [ ] `GET /health` returns 200
- [ ] `lint-imports` passes, and fails on a deliberate violation
- [ ] CI green on first push

**Suggested commit**
```
chore(init): scaffold project structure with enforced clean-architecture layers
```

---

### Phase 2 — Configuration & Environment

**Objective.** One typed, validated, fail-fast configuration object and structured logging with request correlation.

**Overview.** Everything downstream (timeouts, priorities, flags, rule version) reads from `Settings`. Nothing calls `os.environ` outside this module.

**Implementation steps**
1. Implement `Settings(BaseSettings)` in `infrastructure/config/settings.py` covering every variable in §4.1, with types, defaults, and validators (e.g. priority strings parse into lists; TTLs positive).
2. Fail fast at import/startup on missing required values, with a message naming the variable.
3. Provide a cached accessor (`@lru_cache get_settings()`) and a FastAPI dependency.
4. Configure `structlog` in `infrastructure/observability/logging.py`: JSON in production, console locally; bind `request_id`, `path`, `method`.
5. Add middleware generating/propagating `request_id` (surfaces as `metadata.requestId` in API Spec §9.12).
6. Add a redaction processor so keys/secrets never enter logs.

**Files / modules**
`infrastructure/config/settings.py`, `infrastructure/observability/logging.py`, `infrastructure/observability/request_context.py`, `interface/http/dependencies.py` (settings dependency).

**Deliverables.** Typed settings; structured logs carrying `request_id`.

**Testing / verification**
- Unit: valid env parses; missing required var raises at startup; priority string → ordered list.
- Manual: start with `LOG_FORMAT=json`, hit `/health`, confirm one JSON line with a `request_id`.
- Set a fake `LLM_API_KEY` and confirm it is **absent** from all log output.

**Completion checklist**
- [ ] All §4.1 variables represented and typed
- [ ] Startup fails with a clear message when a required var is missing
- [ ] Logs are structured and carry `request_id`
- [ ] No secret appears in any log line

**Suggested commit**
```
feat(config): typed settings, fail-fast validation, structured logging
```

---

### Phase 3 — Database Setup

**Objective.** Persist raw readings and computed intelligence behind repository ports, with migrations.

**Overview.** Implements TRD §7 entities. PostgreSQL doubles as the durable intelligence cache via freshness checks; `rule_config_version` on computed rows makes invalidation correct and determinism auditable.

**Implementation steps**
1. Define the `WeatherRepository` port in `domain/ports/repository.py` (abstract methods only, domain types only).
2. Define SQLAlchemy models in `infrastructure/persistence/models.py`:
   - `locations` — id, name, latitude, longitude, `normalized_key` (unique)
   - `weather_readings_raw` — id, location_id, **provider**, fetched_at, valid_date, raw_payload `JSONB`, normalized_payload `JSONB`
   - `weather_intelligence_daily` — id, location_id, date, risk_level, risk_factors `JSONB`, activity_scores `JSONB`, packing `JSONB`, travel_advisory, `rule_config_version`, generated_at
   - `providers` — name, data_class, priority_order, is_active, last_health_check
3. Add indexes: `(location_id, valid_date)`, `(location_id, date, rule_config_version)`, unique `normalized_key`.
4. Initialize Alembic; generate and review the initial migration by hand.
5. Implement `infrastructure/persistence/repositories.py` fulfilling the port; return **domain objects**, never ORM models.
6. Implement async session management with pooling in `session.py`.

**Files / modules**
`domain/ports/repository.py`, `infrastructure/persistence/{models,repositories,session}.py`, `migrations/versions/0001_initial.py`.

**Deliverables.** Migrated schema; working repositories.

**Testing / verification**
```bash
alembic upgrade head && alembic downgrade -1 && alembic upgrade head
pytest tests/integration/test_repositories.py -q
```
Integration tests (Testcontainers Postgres): round-trip a reading; round-trip intelligence; freshness query returns rows within TTL and excludes stale; a `rule_config_version` change excludes prior rows.

**Completion checklist**
- [ ] Migrations apply and roll back cleanly
- [ ] Repositories return domain objects, not ORM models
- [ ] Freshness and `rule_config_version` filtering verified
- [ ] Indexes present

**Suggested commit**
```
feat(persistence): schema, migrations, and repository implementations
```

---

### Phase 4 — Weather Provider Layer

**Objective.** Four adapters behind one port, each translating exactly one external dialect.

**Overview.** Adapters are the only modules aware of a provider's request format or response shape. They must not compute, cache, or decide.

**Implementation steps**
1. Define the port in `domain/ports/weather_provider.py`:
   ```python
   class DataClass(str, Enum):
       FORECAST = "forecast"
       HISTORICAL = "historical"

   class WeatherProvider(ABC):
       name: str
       data_class: DataClass
       @abstractmethod
       def is_configured(self) -> bool: ...
       @abstractmethod
       async def fetch(self, lat: float, lon: float,
                       start: date, end: date) -> list[NormalizedReading]: ...
   ```
2. Implement `infrastructure/providers/base.py`: shared `httpx.AsyncClient` with timeout, `tenacity` retry on transient errors only, and typed `ProviderError` / `ProviderTimeoutError`.
3. Implement the four adapters (`open_meteo.py`, `openweather.py`, `weatherapi.py`, `meteostat.py`) per §5.2; each maps its condition vocabulary to `WeatherCondition` and returns `NormalizedReading` objects.
4. Set `is_configured()` to `False` when a required key is absent so the registry skips rather than fails (Open-Meteo always returns `True`).
5. Record captured sample payloads into `tests/fixtures/providers/` for offline tests.

**Files / modules**
`domain/ports/weather_provider.py`, `infrastructure/providers/{base,open_meteo,openweather,weatherapi,meteostat}.py`, fixtures.

**Deliverables.** Four independently testable adapters.

**Testing / verification**
Adapter tests with `respx` (no live network): fixture payload in → expected `NormalizedReading` out; unit conversion correct; condition mapping correct; timeout raises `ProviderTimeoutError`; 4xx does **not** retry; 5xx retries then raises.

**Completion checklist**
- [ ] All four adapters implement the port
- [ ] Every provider condition code maps to a `WeatherCondition`
- [ ] Meteostat is marked `HISTORICAL`
- [ ] No adapter imports another adapter
- [ ] Adapter tests pass offline

**Suggested commit**
```
feat(providers): adapters for Open-Meteo, OpenWeather, WeatherAPI, Meteostat
```

---

### Phase 5 — Provider Registry & Fallback

**Objective.** Route by data class and priority, survive provider failure, and expose health — without leaking provider identity into responses.

**Overview.** The registry is the resilience story made concrete. It owns selection, fallback, and health caching; adapters stay dumb.

**Implementation steps**
1. Implement `infrastructure/providers/registry.py` holding adapters keyed by name with `data_class`, priority (from settings), and `is_configured()`.
2. Implement `select(data_class, exclude)` per §5.3: skip unconfigured and unhealthy providers, yield in priority order.
3. Implement `fetch_with_fallback(...)`: iterate the chain; on `ProviderError`/`ProviderTimeoutError`, log with provider name, mark health degraded, advance. Return the first success plus a `used_fallback` flag.
4. Implement health caching (`PROVIDER_HEALTH_TTL_SECONDS`) — a passive health model updated from real call outcomes, plus an on-demand probe for `/providers/health`.
5. Raise `AllProvidersFailedError` when the chain is exhausted; the use case (Phase 7/9) decides between stale-serve and `503`.
6. Guarantee forecast requests never select a `HISTORICAL` provider.

**Files / modules**
`infrastructure/providers/registry.py`, `infrastructure/providers/health.py`, `domain/ports/provider_registry.py`.

**Deliverables.** A registry that degrades predictably.

**Testing / verification**
- Primary fails → second provider used, result returned, `used_fallback=True`.
- All forecast providers fail → `AllProvidersFailedError`.
- Unconfigured provider (no key) is skipped, not attempted.
- A forecast request never selects Meteostat.
- Health reflects real outcomes and respects TTL.

**Completion checklist**
- [ ] Priority order honoured from configuration
- [ ] Fallback advances on failure and timeout
- [ ] Data-class routing enforced
- [ ] Health cached with TTL
- [ ] Provider names appear only in logs/health

**Suggested commit**
```
feat(providers): registry with priority selection, fallback, and health tracking
```

---

### Phase 6 — Response Normalization Engine

**Objective.** One internal weather model, whatever the source.

**Overview.** Normalization is where provider independence becomes structural: after this layer, nothing downstream can tell which provider was used.

**Implementation steps**
1. Define `NormalizedReading` in `domain/entities/weather.py` — a frozen dataclass mirroring API Spec §9.9 fields (`date`, `temp_min_c`, `temp_max_c`, `precipitation_probability`, `precipitation_mm?`, `wind_speed_kph`, `humidity?`, `condition`), plus internal `completeness: float` and `source_class`.
2. Implement unit conversion helpers in `infrastructure/providers/normalization.py`: Kelvin/Fahrenheit → °C, m/s and mph → km/h, percentage → `0.0–1.0`. Convert **once**, at the adapter boundary.
3. Implement condition mapping tables per provider → the `WeatherCondition` enum (API Spec §10). Unmapped codes fall back to the closest supported value and emit a `WARNING` — never crash.
4. Validate ranges: `temp_max_c ≥ temp_min_c`, probabilities within `0.0–1.0`, wind `≥ 0`. Reject a reading that fails validation; if a day is unusable, treat it as missing rather than fabricating values.
5. Compute `completeness` as the fraction of expected optional fields present — this feeds `travelConfidence` in Phase 7.

**Files / modules**
`domain/entities/weather.py`, `infrastructure/providers/normalization.py`, `infrastructure/providers/condition_maps.py`.

**Deliverables.** A validated, provider-agnostic reading model.

**Testing / verification**
Parameterized unit tests per provider fixture asserting identical `NormalizedReading` output for equivalent weather across all four providers — the definitive provider-independence test. Plus conversion tables, validation rejection, and unknown-code fallback.

**Completion checklist**
- [ ] All providers yield identical model shapes
- [ ] Conversions correct and applied once
- [ ] Every enum value reachable from at least one provider mapping
- [ ] Invalid readings rejected, not silently coerced
- [ ] `completeness` computed

**Suggested commit**
```
feat(normalization): unified weather model with conversion, mapping, and validation
```

---

### Phase 7 — Weather Intelligence Engine

**Objective.** The deterministic core: risk, activity suitability, packing, best/worst days, trip scores. **No AI, no I/O.**

**Overview.** This is the product. Every function here is pure: `(readings, rule_config) → intelligence`. If anything in `domain/engines/` touches the network, a clock, or randomness, it is wrong.

**Processing pipeline**
```
NormalizedReading[]
  → Insight Engine
      rules.py    : evaluate thresholds → triggered rule ids
      risk.py     : rule ids → RiskFactor[] → RiskLevel (max severity)
      scoring.py  : summary + rules → ActivitySuitability[] (0–100)
      → DailyIntelligence[] (+ travelAdvisory from RiskLevel)
  → Recommendation Engine
      best_worst.py  : rank days by suitability/risk → bestDays, worstDays
      packing.py     : union of daily items, deduplicated, stable order
      trip_scores.py : overallRiskLevel, tripSuitabilityScore, travelConfidence
      → TripSummary
  → Intelligence Builder → WeatherIntelligence (narrative = None)
```

**Implementation steps**
1. Author `infrastructure/config/rule_config/2026.07.yaml` holding every threshold, activity weight, and confidence weight. Load and validate it into a typed `RuleConfig`; stamp `RULE_CONFIG_VERSION` on all output.
2. Implement `engines/insight/rules.py`: pure predicates producing stable rule ids (e.g. `precip_prob_gt_0_6`). Each triggered rule yields a `RiskFactor` carrying its `rule` id — this satisfies explainability (NFR-1) and is asserted in tests.
3. Implement `engines/insight/risk.py`: factors → `RiskLevel` by maximum severity; map to `TravelAdvisory` (`low→proceed`, `moderate→caution`, `high→avoid`) per API Spec §10.
4. Implement `engines/insight/scoring.py`: per `ActivityCategory` (`outdoor_sightseeing`, `beach`, `indoor_museum`), start from a base score and apply config-driven penalties/bonuses; clamp to `0–100` and round deterministically.
5. Implement `engines/recommendation/best_worst.py`: rank days with a **deterministic tie-breaker** (earlier date wins) so output never depends on sort stability.
6. Implement `engines/recommendation/packing.py`: union daily recommendations; deduplicate; return in a stable configured order.
7. Implement `engines/recommendation/trip_scores.py`:
   - `overallRiskLevel` — worst-case: maximum daily risk.
   - `tripSuitabilityScore` — weighted average of daily suitability, `0–100`.
   - `travelConfidence` — `0.0–1.0` from three inputs, weights in rule config (TRD §7.5): **(a)** forecast horizon (further out → lower), **(b)** inter-source agreement (single source → fixed neutral factor; MVP typically single-provider), **(c)** mean `completeness` from normalization.
8. Implement the builder in `domain/entities/weather_intelligence.py`; set `narrative = None` — the builder never calls AI.

**Files / modules**
`domain/engines/insight/{rules,risk,scoring}.py`, `domain/engines/recommendation/{best_worst,packing,trip_scores}.py`, `domain/rules/config.py`, `infrastructure/config/rule_config/2026.07.yaml`, `domain/entities/weather_intelligence.py`.

**Deliverables.** A complete deterministic engine, fully unit-tested offline.

**Testing / verification**
- Table-driven cases: clear day, storm day, and **threshold-boundary** days (exactly at each cutoff).
- **Determinism test:** run the same input 100× and assert byte-identical output.
- **Explainability test:** every emitted `RiskFactor` has a non-empty `rule` id present in the rule config.
- **Golden files:** snapshot expected intelligence for fixed inputs + `rule_config_version`; any drift fails (regression).
- Confidence test: longer horizon and lower completeness both reduce `travelConfidence`, monotonically.

```bash
pytest tests/domain -q          # must pass with networking disabled
```

**Completion checklist**
- [ ] `domain/engines/` performs no I/O and imports no framework
- [ ] Every factor carries a rule id
- [ ] Thresholds live in YAML, not code
- [ ] Determinism and golden-file tests pass
- [ ] Advisory mapping matches API Spec §10
- [ ] `travelConfidence` uses all three inputs

**Suggested commit**
```
feat(engines): deterministic insight and recommendation engines with versioned rule config
```

---

### Phase 8 — AI Narration Service

**Objective.** Optional natural-language restatement of finished intelligence. It **never** computes, ranks, or alters a value.

**Overview.** Narration is an infrastructure adapter behind `NarrationPort`, called by exactly one use case. The `narrative` field is the only thing it may produce. With `NARRATION_ENABLED=false`, the entire product still works — that switch is the proof of the boundary.

**Implementation steps**
1. Define `domain/ports/narration.py`:
   ```python
   class NarrationPort(ABC):
       @abstractmethod
       async def narrate(self, intelligence: WeatherIntelligence,
                         language: str = "en") -> Narrative: ...
   ```
2. Implement `infrastructure/ai/prompts/narration.j2` (or a plain template): a system instruction stating the model receives **already-computed** intelligence and must not add, change, or infer any number, ranking, or recommendation absent from the input; the intelligence object is passed as structured JSON.
3. Implement `infrastructure/ai/llm_client.py`: thin HTTP client with `LLM_TIMEOUT_SECONDS`, output token cap, and at most one retry. **No orchestration framework** (Bible ADR-006/011).
4. Implement `infrastructure/ai/narration_service.py` fulfilling the port: build prompt → call → validate → return `Narrative(generated_by_llm=True, summary_text=..., model_used=..., fallback_used=False)`.
5. Implement `infrastructure/ai/fallback.py`: a deterministic template composed from the same object — best day, worst day, overall risk, top packing items — returning `generated_by_llm=False, model_used=None, fallback_used=True`.
6. Trigger the fallback on: flag disabled, timeout, transport error, empty/over-long output, or missing API key. **Never raise to the caller** — narration failure is a `200` with a fallback.
7. Cache narration keyed on `(location, period, rule_config_version, language)`.
8. Treat output as untrusted text: length-cap it and write it only to `narrative.summary_text`. There is no write path to any computed field.

**Files / modules**
`domain/ports/narration.py`, `infrastructure/ai/{llm_client,narration_service,fallback}.py`, `infrastructure/ai/prompts/`.

**Deliverables.** Optional narration with a guaranteed deterministic fallback.

**Testing / verification**
- **AI-output validation (highest-signal test):** narrate a fixed intelligence object, then deep-diff input vs output — **only `narrative` may differ.** Fail otherwise.
- Fallback tests: flag off; injected timeout; injected 500; empty response — all return `200` with `fallback_used=True`.
- Prompt snapshot test: assembled prompt contains the object and the "do not alter" instruction.
- Injection test: an LLM response attempting to restate scores cannot change any computed field (structurally guaranteed; assert it).

**Completion checklist**
- [ ] `NARRATION_ENABLED=false` → full product works, all tests pass
- [ ] Narration writes only `narrative`
- [ ] Every failure mode yields a templated fallback, never an exception
- [ ] Prompts are versioned files, not inline strings
- [ ] Narration cached

**Suggested commit**
```
feat(ai): narration service with constrained prompt and deterministic fallback
```

---

### Phase 9 — REST API Implementation

**Objective.** Implement the API Spec (`04`) exactly — six endpoints, one envelope, one error contract.

**Overview.** Controllers stay thin: validate, delegate to a use case, wrap in the envelope. All business logic already exists in Phases 5–8.

**Endpoints (API Spec §8)**
| Method | Path | Use case |
|---|---|---|
| GET | `/api/v1/locations/{locationId}/intelligence` | `GetWeatherIntelligence` |
| GET | `/api/v1/locations/{locationId}/intelligence/best-days` | `GetBestDays` |
| GET | `/api/v1/locations/{locationId}/intelligence/packing` | `GetPacking` |
| GET | `/api/v1/locations/{locationId}/weather/raw` | `GetRawWeather` |
| POST | `/api/v1/locations/{locationId}/intelligence/narrative` | `GenerateNarrative` |
| GET | `/api/v1/providers/health` | `GetProviderHealth` (ops key) |

**Implementation steps**
1. Implement Pydantic response schemas in `interface/http/schemas/` mirroring API Spec §9 **field-for-field**, including `camelCase` aliases (`alias_generator` + `populate_by_name`) — internal snake_case, external camelCase.
2. Implement `interface/http/envelope.py`: build `{success, data, metadata, error}` with `apiVersion`, `generatedAt`, `requestId`, `cacheStatus`, `ruleConfigVersion`, `degraded`. **Never include provider identity.**
3. Implement `dependencies.py`: `X-API-Key` auth (401 on missing/invalid), ops-key check for `/providers/health`, shared query-param validation for `startDate`/`endDate`.
4. Implement validation per API Spec §11: `locationId` parses to `lat,lon` with range checks; ISO dates; `startDate ≤ endDate`; span ≤ `MAX_FORECAST_HORIZON_DAYS`. Reject **before** any provider or DB call.
5. Implement use cases in `application/use_cases/`: read store → on miss/stale, fetch via registry → normalize → persist → compute → persist → build. Best-days and packing are projections of the same computation — do not duplicate logic.
6. Implement `errors.py` exception handlers mapping to API Spec §7: `VALIDATION_ERROR` 400, `AUTHENTICATION_ERROR` 401, `NOT_FOUND` 404, `RATE_LIMITED` 429, `PROVIDER_UNAVAILABLE`/`SERVICE_DEGRADED` 503, `INTERNAL_ERROR` 500. Never leak stack traces or provider detail.
7. Implement degraded responses: stale-serve returns `200` with `degraded: true`, `cacheStatus: "stale"`.
8. Add per-key rate limiting (`RATE_LIMIT_PER_MINUTE`) returning `429` with `Retry-After`.
9. Confirm generated OpenAPI at `/docs` matches document `04`.

**Files / modules**
`interface/http/routers/*.py`, `interface/http/schemas/*.py`, `envelope.py`, `errors.py`, `dependencies.py`, `application/use_cases/*.py`.

**Deliverables.** A complete, contract-conformant API.

**Testing / verification**
- API tests per endpoint: 200 shape, 400 invalid dates/coords, 401 missing key, 404 unresolvable, 429 over limit.
- Envelope test: every response — success and error — has all four envelope keys.
- **Provider-independence test:** assert no response body from any weather endpoint contains any provider name.
- Contract test: validate responses against JSON Schemas derived from API Spec §9; a breaking change fails the build.
- `narrative` is `null` on `GET /intelligence`; populated only via `POST /narrative`.

**Completion checklist**
- [ ] All six endpoints implemented at the documented paths
- [ ] camelCase external / snake_case internal
- [ ] All error codes and statuses match §7
- [ ] Validation precedes all I/O
- [ ] No provider name in any weather response
- [ ] `/docs` matches document `04`

**Suggested commit**
```
feat(api): implement v1 REST endpoints per API & Data Contract Specification
```

---

### Phase 10 — Frontend Assistant Integration

**Objective.** A chat-style Weather Intelligence Assistant that renders deterministic intelligence as structured cards, with narration as an optional enhancement.

**Scope boundary (read before implementing).** Bible §11 and PRD §11 exclude open-ended conversational AI, and that exclusion holds. This is a **domain-scoped assistant**, not a general chatbot:

| Build this | Do not build this |
|---|---|
| Each turn extracts `(location, dates)` from user text | Free-form Q&A on arbitrary topics |
| Every turn maps to one deterministic API call | An LLM agent that answers from its own knowledge |
| LLM does parameter extraction + optional narration | LLM that computes risk, ranks days, or advises |
| Structured cards are the primary output | A wall of generated prose |
| Form inputs always available as a fallback path | A chat-only interface with no deterministic path |

**Request flow**
```
User message ("I'm travelling to Goa Aug 1–5")
  → Assistant UI
  → Frontend validation (non-empty, length cap)
  → Intent extraction  →  { location: "Goa", startDate, endDate }
  → Geocode "Goa" → 15.2993,74.1240        (client responsibility, API Spec §5)
  → GET /api/v1/locations/{lat,lon}/intelligence?startDate&endDate
  → Backend: providers → normalization → intelligence engine
  → JSON envelope → render structured cards
  → (optional) POST .../narrative → render AI Explanation panel
```

**Implementation steps**
1. **Client**: single-page app (React + Vite). Configure `VITE_API_BASE_URL`. **Never ship the API key in browser code** — route calls through a small backend-for-frontend or proxy that injects `X-API-Key` (API Spec §3).
2. **Intent extraction**: parse user text to `{location, startDate, endDate}`. Two supported approaches — a date-parsing library plus place-name extraction, or a constrained LLM call returning **JSON only**. Either way: validate the result against a strict schema, and if extraction fails or is ambiguous, fall back to the form inputs rather than guessing. Extraction never produces weather values.
3. **Geocoding**: resolve the place name to `lat,lon` client-side (API Spec §5 makes this a client responsibility). Cache resolutions.
4. **State management**: keep a turn list. Each turn holds `{ userText, params, status, intelligence, narrative, error }`. Status is one of `idle | extracting | fetching | ready | narrating | error`. Keep API responses in state exactly as returned; derive display values, never mutate.
5. **Loading states**: skeleton cards while `fetching`; a separate, smaller spinner on the AI Explanation panel while `narrating`. **Render the deterministic cards as soon as they arrive — never block them on narration.**
6. **Rendering — deterministic first**:
   - *Trip Summary card*: `overallRiskLevel`, `tripSuitabilityScore`, `travelConfidence`, best/worst days.
   - *Forecast cards*: one per `dailyIntelligence` entry — temps, precipitation, wind, condition.
   - *Risk panel*: level plus factor chips; show each factor's `description`, and expose its `rule` id in a tooltip or details view (explainability made visible).
   - *Activity suitability*: bars per category, `0–100`.
   - *Packing*: `overallPackingList`, with per-day items on the day cards.
7. **Narration panel**: an explicit "Explain this trip" action issuing `POST .../narrative`. When `fallbackUsed: true`, render the text plainly without AI attribution. Label the panel **"AI Explanation"** — never "advice" or "advisor" (Bible ADR-005/010).
8. **Confidence display**: surface `travelConfidence` as a plain-language qualifier ("forecast confidence: moderate") so users don't over-trust long-range results.
9. **Error handling**: map API Spec §7 codes to user-facing messages — `VALIDATION_ERROR` → inline field hint; `RATE_LIMITED` → "try again shortly"; `PROVIDER_UNAVAILABLE` → "weather data temporarily unavailable"; `INTERNAL_ERROR` → generic message plus `requestId` for support. Never surface raw error payloads.
10. **Degraded handling**: when `metadata.degraded` is `true` or `cacheStatus` is `"stale"`, render a subtle "showing last available data" badge — still show the full analysis.
11. **Retry behaviour**: exponential backoff with jitter on `429`/`503`/network errors only; honour `Retry-After`; never auto-retry `400`/`401`. Cap at two automatic attempts, then offer a manual retry.
12. **Enum tolerance**: unknown `WeatherCondition` or `ActivityCategory` values must render a neutral default rather than crashing (API Spec §12 forward compatibility).

**Combining structured data and narration.** The structured response is the source of truth for everything displayed as a number, level, or ranking. The narrative is presentational text placed in its own panel. The UI must never parse the narrative to obtain a value, and must never display a number that came from the narrative rather than the structured payload.

**Files / modules**
`frontend/src/api/client.ts`, `frontend/src/api/types.ts` (generated from or mirroring API Spec §9), `frontend/src/features/assistant/{ChatPanel,TurnList,IntentInput}.tsx`, `frontend/src/features/intelligence/{TripSummaryCard,ForecastCards,RiskPanel,ActivityBars,PackingList,ExplanationPanel}.tsx`, `frontend/src/state/turns.ts`.

**Deliverables.** A working assistant UI over the v1 API.

**Testing / verification**
- Component tests with mocked API responses: success, degraded, each error code.
- **AI-off test:** set `NARRATION_ENABLED=false`; the UI must remain fully usable and every card must render.
- Extraction tests: representative phrasings map to the correct params; ambiguous input falls back to the form.
- Verify no API key is present in the built bundle (`grep` the build output).

**Completion checklist**
- [ ] Deterministic cards render before and independently of narration
- [ ] No API key in client bundle
- [ ] All API Spec §7 error codes handled
- [ ] Degraded/stale badge implemented
- [ ] Panel labelled "AI Explanation", not "advice"
- [ ] Unknown enum values do not crash the UI
- [ ] No displayed number is derived from narrative text

**Suggested commit**
```
feat(frontend): weather intelligence assistant with structured rendering and optional narration
```

---

### Phase 11 — Testing & Validation

**Objective.** Complete the suite defined in TRD §13 and make correctness enforceable in CI.

**Test layout**
| Layer | Location | Runs offline | Focus |
|---|---|---|---|
| Domain unit | `tests/domain/` | **yes** | engines, rules, scoring, determinism |
| Provider adapters | `tests/providers/` | yes (`respx`) | normalization per provider |
| Integration | `tests/integration/` | needs containers | repositories, cache, use cases |
| API | `tests/api/` | yes (deps mocked) | contract, envelope, errors, auth |
| Contract/regression | `tests/api/test_contract.py`, golden files | yes | schema stability, output drift |

**Implementation steps**
1. **Mock providers**: implement a `FakeProvider` fulfilling the port with scriptable behaviours — success, timeout, 5xx, malformed payload — so registry and fallback logic are tested without network.
2. **Unit**: table-driven engine tests including boundary values; the 100×-identical determinism assertion.
3. **Integration**: Testcontainers Postgres + Redis; verify persistence, freshness, `rule_config_version` invalidation, and cache hit/miss/stale transitions.
4. **API**: `httpx.AsyncClient` against the app; assert status codes, envelope keys, camelCase field names, and error codes.
5. **Error scenarios**: all providers down → 503; primary down → fallback 200; LLM down → 200 with `fallbackUsed`; DB down → controlled 503; invalid key → 401.
6. **Edge cases**: single-day range; maximum-horizon range; range partially beyond horizon; leap day; equal `startDate`/`endDate`; a location with missing optional fields (low completeness → lower `travelConfidence`); unmapped provider condition code.
7. **Coverage gate**: enforce high coverage on `app/domain/` specifically; do not chase coverage on infrastructure glue.

**Deliverables.** A complete, CI-enforced test suite covering all six layers, with the domain suite runnable offline.

**Verification checklist**
- [ ] `pytest tests/domain -q` passes with networking disabled
- [ ] `NARRATION_ENABLED=false` → full suite passes
- [ ] AI-output diff test passes (only `narrative` differs)
- [ ] Fallback and timeout paths covered for providers and LLM
- [ ] No provider name in any weather-endpoint response body
- [ ] Golden-file regression passes
- [ ] CI runs lint, types, `lint-imports`, and tests on every push

**Suggested commit**
```
test: complete unit, provider, integration, API, and contract test suites
```

---

### Phase 12 — Docker & Deployment

**Objective.** Reproducible container build and a documented deployment workflow.

**Dockerfile** (`docker/Dockerfile`) — multi-stage, non-root:
```dockerfile
FROM python:3.11-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime
RUN useradd -m -u 1000 appuser
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini ./
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import httpx;httpx.get('http://localhost:8000/health',timeout=2)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
```

**docker-compose.yml** (local):
```yaml
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: wis
      POSTGRES_PASSWORD: wis
      POSTGRES_DB: wis
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL","pg_isready -U wis"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD","redis-cli","ping"]
      interval: 5s
      retries: 5

  api:
    build: { context: ., dockerfile: docker/Dockerfile }
    env_file: [.env]
    ports: ["8000:8000"]
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }

volumes: { pgdata: {} }
```

**Running locally**
```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose logs -f api
```

**Production environment variables.** Same keys as §4.2 with: `APP_ENV=production`, `LOG_FORMAT=json`, `LOG_LEVEL=INFO`, strong `API_KEYS`/`OPS_API_KEYS`, managed `DATABASE_URL` and `REDIS_URL`, real provider and LLM keys. Inject via the platform's secret store — **never** bake `.env` into the image.

**Deployment workflow**
1. CI green (lint, mypy, `lint-imports`, tests).
2. Build and tag the image with the commit SHA.
3. Push to the registry.
4. Run `alembic upgrade head` against the target database **before** releasing the new image.
5. Deploy (single container + managed Postgres/Redis on a small PaaS, per TRD §14 — no orchestration platform at this scope).
6. Verify (below); roll back to the previous tag on failure.

**Deliverables.** A reproducible non-root container image, a local compose stack, and a documented, verifiable deployment workflow.

**Deployment verification**
```bash
curl -sf https://<host>/health
curl -s -H "X-API-Key: $KEY" \
  "https://<host>/api/v1/locations/15.2993,74.1240/intelligence?startDate=<d1>&endDate=<d2>" | jq '.success'
curl -s -H "X-API-Key: $OPS_KEY" https://<host>/api/v1/providers/health | jq .
```

**Completion checklist**
- [ ] Image builds and runs as non-root
- [ ] Compose brings up API + Postgres + Redis with healthchecks
- [ ] Migrations run before release
- [ ] HTTPS enforced; secrets injected, not baked
- [ ] Health and a real intelligence call verified post-deploy
- [ ] Rollback procedure documented

**Suggested commit**
```
chore(deploy): container build, compose stack, and deployment workflow
```

---

## 8. Logging & Error Handling

### 8.1 Structured logging
Every log line is a structured event (`structlog`), JSON in production. Bind `request_id` at middleware and propagate it through use cases so one request is traceable end to end. `request_id` is returned as `metadata.requestId`, which is what a consumer quotes in a support request.

**Always log:** external call outcomes (provider name, duration, status, attempt number), cache hit/miss/stale, fallback activation, narration fallback, `rule_config_version` on compute.
**Never log:** API keys, LLM keys, full prompts or completions that could contain user trip context, connection strings.

### 8.2 Log levels
| Level | Use |
|---|---|
| `DEBUG` | Local diagnostics; disabled in production |
| `INFO` | Request lifecycle, cache outcomes, provider selection |
| `WARNING` | Retry, fallback used, unmapped condition code, stale-serve |
| `ERROR` | Provider chain exhausted, DB failure, unhandled exception |
| `CRITICAL` | Startup failure (missing required configuration) |

### 8.3 Centralized exception handling
Register handlers in `interface/http/errors.py` — a single mapping from internal exception types to the API Spec §7 contract. Domain and infrastructure raise **typed** exceptions (`ProviderError`, `AllProvidersFailedError`, `ValidationError`, `RepositoryError`); only the handler layer knows HTTP. No `try/except` blocks scattered through routers.

### 8.4 Failure behaviour
| Failure | Behaviour | Client sees |
|---|---|---|
| Single provider fails/times out | log `WARNING`, mark health, advance chain | `200` (normal) |
| All forecast providers fail, stored data exists | serve stale | `200`, `degraded: true`, `cacheStatus: "stale"` |
| All fail, no stored data | log `ERROR` | `503 PROVIDER_UNAVAILABLE` |
| LLM disabled/fails/times out | templated fallback | `200`, `fallbackUsed: true` |
| DB unavailable | log `ERROR`, controlled failure | `503` |
| Unhandled exception | log `ERROR` with `request_id` | `500 INTERNAL_ERROR`, no internals leaked |

### 8.5 Retry strategy
Provider: `PROVIDER_RETRY_ATTEMPTS` on transient errors (connection, timeout, 5xx) with exponential backoff; never on 4xx; retries do not stack with fallback. LLM: at most one retry — narration is optional and not worth the latency.

### 8.6 Health checks
`GET /health` — liveness, no dependencies, used by the container healthcheck. `GET /api/v1/providers/health` — ops-only provider availability (the sole endpoint permitted to name providers).

---

## 9. Security Best Practices

| Area | Practice |
|---|---|
| **API key protection** | Consumer keys on `X-API-Key`; compare in constant time; never log. Browser clients call through a proxy/BFF — a key in frontend code is a leaked key. |
| **Environment variables** | All secrets from env; `.env` git-ignored; only `.env.example` committed with empty values. Verify with `git log -p --all -- .env` before publishing. |
| **Input validation** | Validate at the HTTP boundary before any I/O: coordinate ranges, ISO dates, ordering, horizon cap. Reject rather than clamp. |
| **Secure configuration** | Fail fast on missing required config. No debug mode, no `--reload`, and no interactive docs exposure decisions left to chance in production. |
| **HTTPS** | Required in all deployed environments; terminate at the platform edge; redirect HTTP. |
| **Secret management** | Platform secret store in production; rotate provider and LLM keys periodically; never bake secrets into images. |
| **Safe logging** | Redaction processor for known secret keys; never log prompts/completions containing trip context; log `request_id`, not user text. |
| **LLM output** | Treated as untrusted: length-capped, written only to `narrative.summary_text`. There is no write path from model output to a computed field — prompt injection cannot alter a decision. |
| **Rate limiting** | Per-key limits protect both this service and upstream provider quotas. |
| **Dependencies** | Pin versions; run a vulnerability scan in CI; update deliberately. |

---

## 10. Troubleshooting Guide

| Symptom | Likely cause | Resolution |
|---|---|---|
| `ValidationError` at startup naming a variable | Missing required env var | Copy `.env.example` → `.env`; set `DATABASE_URL`, `REDIS_URL`, `API_KEYS` |
| `401 AUTHENTICATION_ERROR` on every call | Missing/incorrect `X-API-Key` | Send a key listed in `API_KEYS`; check for whitespace in the env value |
| `403` on `/providers/health` | Using a consumer key | Use a key from `OPS_API_KEYS` |
| All requests `503 PROVIDER_UNAVAILABLE` | No provider reachable/configured | Confirm outbound network; Open-Meteo needs no key — if it fails, the issue is connectivity, not credentials |
| One provider always skipped | `is_configured()` false | Set that provider's API key, or accept the skip (by design) |
| `401`/`403` from a provider in logs | Invalid or unactivated provider key | Re-issue the key; new OpenWeather keys can take time to activate |
| Provider returns data but fields are empty | Condition/field mapping gap | Check `WARNING` logs for unmapped codes; extend the mapping table (Phase 6) |
| `asyncpg.InvalidCatalogNameError` | Database not created | `docker compose up -d postgres`; confirm `POSTGRES_DB` matches `DATABASE_URL` |
| `Connection refused` on 5432 | Postgres not ready | `docker compose ps`; wait for healthcheck; check port conflicts |
| Alembic "target database is not up to date" | Pending migrations | `alembic upgrade head` |
| Alembic autogenerate produces an empty migration | Models not imported in `env.py` | Import all models in Alembic's `env.py` metadata |
| `redis.exceptions.ConnectionError` | Redis down or wrong URL | `docker compose up -d redis`; verify `REDIS_URL`; temporarily set `CACHE_BACKEND=memory` to isolate |
| Stale results after changing a threshold | Cache keyed on old rule version | Bump `RULE_CONFIG_VERSION`; this invalidates computed intelligence by design |
| `ImportError` / `ModuleNotFoundError` on start | venv not activated or package not installed | `source .venv/bin/activate`; `pip install -e ".[dev]"` |
| `lint-imports` fails | A layer boundary was violated | Move the offending import; do not relax the contract |
| Uvicorn `Address already in use` | Port 8000 taken | `lsof -i :8000`; kill or change `APP_PORT` |
| `--reload` not detecting changes (Windows) | Running on native Windows filesystem | Develop inside WSL2 |
| Docker build fails on dependency install | Stale layer cache | `docker compose build --no-cache` |
| Container exits immediately | Missing env or failed migration | `docker compose logs api`; verify `env_file` and run migrations |
| Narration always returns fallback | Flag off, missing key, or timeout | Check `NARRATION_ENABLED`, `LLM_API_KEY`; raise `LLM_TIMEOUT_SECONDS`; **note this is correct degradation, not a crash** |
| Frontend `CORS` errors | Origin not allowed | Configure CORS middleware for the frontend origin |
| Different results for identical inputs | Non-determinism in the domain | Search `domain/` for `datetime.now`, `random`, or unstable sorts — determinism is a hard requirement |

---

## 11. Appendix

### 11.1 Terminal commands
```bash
source .venv/bin/activate                 # activate environment
pip install -e ".[dev]"                   # install with dev extras
ruff check . --fix && ruff format .        # lint + format
mypy app                                   # type check
lint-imports                               # verify layer boundaries
pytest -q                                  # all tests
pytest tests/domain -q                     # offline domain tests
pytest --cov=app/domain --cov-report=term  # domain coverage
```

### 11.2 Git commands
```bash
git checkout -b feat/phase-07-engines
git add -A && git commit -m "feat(engines): deterministic insight engine"
git push -u origin feat/phase-07-engines
git log --oneline --graph --decorate -20
```

### 11.3 FastAPI / Uvicorn
```bash
uvicorn app.main:app --reload --port 8000          # dev
uvicorn app.main:app --host 0.0.0.0 --workers 4    # prod-like
open http://localhost:8000/docs                    # Swagger UI
curl -s localhost:8000/openapi.json | jq .          # generated spec
```

### 11.4 Docker
```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api
docker compose exec api alembic upgrade head
docker compose exec api sh
docker compose down -v            # WARNING: -v deletes volumes
docker system prune -f
```

### 11.5 PostgreSQL
```bash
docker compose exec postgres psql -U wis -d wis
\dt                                        # list tables
\d weather_intelligence_daily              # describe table
SELECT date, risk_level, rule_config_version
  FROM weather_intelligence_daily ORDER BY date LIMIT 10;
alembic upgrade head / downgrade -1
alembic revision --autogenerate -m "add x"
```

### 11.6 Redis
```bash
docker compose exec redis redis-cli
PING
KEYS 'wis:*'                               # dev only — never in production
TTL <key>
FLUSHDB                                    # dev only
INFO stats                                 # hit/miss ratio
```

### 11.7 Development checklist
- [ ] Virtual environment active; dependencies installed
- [ ] `.env` configured; Postgres and Redis healthy
- [ ] Migrations applied
- [ ] `ruff`, `mypy`, `lint-imports` clean
- [ ] `pytest tests/domain` passes offline
- [ ] New thresholds added to rule config, not to code
- [ ] No provider name in any weather-endpoint response
- [ ] `NARRATION_ENABLED=false` still yields a fully working product

### 11.8 Deployment checklist
- [ ] CI green on the release commit
- [ ] Image tagged with commit SHA; built as non-root
- [ ] Production secrets in the platform secret store; no `.env` in the image
- [ ] `alembic upgrade head` run before release
- [ ] HTTPS enforced
- [ ] `/health` and a real intelligence call verified post-deploy
- [ ] `/providers/health` shows expected availability
- [ ] Logs are JSON and carry `request_id`; no secrets present
- [ ] Rollback tag identified

### 11.9 Glossary
| Term | Meaning |
|---|---|
| Adapter | Module translating one external provider's dialect into the internal model. |
| Data class | `forecast` or `historical`; governs provider routing. |
| Determinism | Identical inputs and rule version always produce identical output. |
| Degraded response | Valid data served in a reduced mode (stale or fallback), flagged in `metadata`. |
| Fallback (narration) | Deterministic templated text returned when the LLM is unavailable. |
| Golden file | Stored expected output used to detect unintended engine changes. |
| Normalization | Conversion of provider payloads into the single internal reading model. |
| Port | Abstract interface defined in `domain/ports`, implemented in `infrastructure`. |
| Provider independence | No weather-data response reveals which provider supplied the data. |
| Rule config version | Identifier of the active rule set; stamped on computed rows; drives invalidation. |
| Travel confidence | `0.0–1.0` trust indicator from horizon, source agreement, and data completeness. |

---

*End of Implementation & Development Guide v1.0. This document implements the decisions recorded in `01`–`04` and does not modify them, with the two exceptions declared in §1.6, which require an ADR supersession entry in the Project Bible.*
