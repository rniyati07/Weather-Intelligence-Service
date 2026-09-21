# Live smoke suite

Formalizes ISSUE-9 from `docs/WEATHER_INTELLIGENCE_FULL_E2E_AUDIT.md` ("no
live-service or frontend integration tests") — the scenarios manually
verified against the real running stack on 2026-09-20, captured as repeatable
tests instead of one-off curl commands.

**This suite makes real calls to Groq, Open-Meteo, and Overpass, and writes
to a real database.** It is deliberately excluded from the default `pytest`
run (`addopts = -m "not live"` in `pyproject.toml`) and from CI — nothing
here may run without real credentials, and external-provider flakiness
(rate limits, timeouts — see ISSUE-2/ISSUE-8 in the audit) must never fail a
normal build.

## Running it

Requires a real `.env` (`LLM_API_KEY`, `DATABASE_URL` pointing at a live,
migrated Postgres) — the same one used for local dev, not CI's placeholder
values.

```bash
alembic upgrade head   # if not already applied
pytest -m live tests/live -v
```

## What it checks

Structural/behavioral assertions, not exact content — an LLM's exact wording
and Overpass's exact result count vary between runs by design (see the
audit's §21, "External limitations"). A test here fails only on things that
indicate a real regression: a crash, a wrong intent classification, a
destination/context field that should have survived a turn but didn't, a
place with a category outside what was actually requested.
