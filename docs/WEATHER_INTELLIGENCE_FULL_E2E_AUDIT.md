# Weather Intelligence — Full End-to-End Audit

**Audit date:** 2026-09-15
**Scope:** Frontend + backend + external providers, as they exist in the working tree at time of audit.
**Nature:** Forensic audit. No production code, prompt, schema, contract, configuration or provider logic was modified. This document is the only artefact created.
**Method:** Live execution against the running stack (FastAPI on `:8000`, Vite on `:5173`, PostgreSQL on `:5432`), real external providers, real browser interaction with network and console instrumentation. Prior reports were treated as unverified claims and re-tested from scratch.

---

## 1. Executive summary

The system is **genuinely functional end to end**. The frontend is really connected to the backend; the numbers, days, places and packing rendered in the UI were traced to live API payloads with no mock interception and no locally-invented facts. The intelligence engine computes from real forecast data, conversation state persists in PostgreSQL, and the LLM understands multi-turn context including date changes, pace changes and destination changes.

Three findings matter.

1. **One real application bug (HIGH).** When the user names an ambiguous destination mid-trip ("Let's go to Paris instead"), the backend deliberately clears the resolved destination to force disambiguation. The frontend derives its whole workspace from that field, so a trip that had been established for nine turns loses its entire Trip Intelligence layer — outlook, days, places, packing and trip identity all disappear while 21 messages remain on screen. Reproduced in the browser.

2. **Places are governed by external reliability and real OSM data density, not by an application defect.** The pipeline is correct: query construction, `nwr` element selection, parsing, the drop-unnamed filter, persistence and frontend retention all verified working. Four of five destinations returned 34–40 real places. The two observed failure modes are Overpass returning `429`/`504` under load, and genuine OSM sparsity at Goa's coordinates.

3. **The Overpass mirror added as a fallback is effectively dead** and is now a latency cost rather than a safety net. Measured independently: primary `200` in 1.1s, mirror `ReadTimeout` after 40.5s. This is the direct cause of 73–81s chat turns.

The most misleading surface in the system is `GET /providers/health`: it reports all four weather providers as `available` when three of them have never been called. That is a passive-cache artefact, not a verified health signal.

**Overall health: good, with one HIGH-severity UX bug and a self-inflicted latency regression.**

---

## 2. Current system architecture

| Layer | Implementation | Verified state |
|---|---|---|
| Frontend | React 19 + Vite + TS (strict) + Tailwind 4 + TanStack Query + React Router | Running, 0 console errors |
| BFF / proxy | Vite dev proxy injects `X-API-Key` server-side | Working; no key in client bundle |
| API | FastAPI, `/api/v1`, envelope `{success,data,metadata,error}` | Working |
| Orchestration | `ChatOrchestrator` — single orchestrator, 2 LLM calls/turn | Working |
| LLM | Groq, `openai/gpt-oss-20b`, OpenAI-compatible | Working, 0.5s on a trivial call |
| Geocoding (chat) | `AliasedGeocoding` → `OpenMeteoGeocoding` (backend) | Working |
| Geocoding (`/plan`) | Open-Meteo direct from browser | Working (real, despite a stale "mocked" comment) |
| Weather | Registry: `open_meteo` → `openweather` → `weatherapi` | `open_meteo` serving; fallbacks unexercised |
| Intelligence | Deterministic rule engine, `rule_config/2026.07.yaml` | Working, deterministic |
| Places | Overpass (`overpass-api.de`, mirror `overpass.kumi.systems`) | Primary working; mirror dead |
| Persistence | PostgreSQL via SQLAlchemy async (asyncpg) | Working |

---

## 3. End-to-end data flow (verified)

```
USER → ChatComposer.submit
     → useSendChatMessage → POST /api/v1/conversations/chat  (via Vite proxy, +X-API-Key)
     → ChatOrchestrator.process_message
         → EntityExtractor._llm_extract   (Groq, json_mode)      [VERIFIED]
         → AliasedGeocoding.search                                [VERIFIED]
         → TripContext.merge + date validation                    [VERIFIED]
         → intent resolution                                      [PARTIAL — see ISSUE-5]
         → GetWeatherIntelligence → provider registry → open_meteo [VERIFIED]
         → rule engine (risk/score/confidence/packing/best-worst)  [VERIFIED]
         → PlacesBackedAttractionProvider → Overpass               [EXTERNAL-DEPENDENT]
         → _generate_conversational_narrative (Groq)               [VERIFIED]
         → conversation_repo.save (messages + metadata + context)  [VERIFIED]
     → ChatResponse
     → ChatPage: latestTripContext / latestPlaces / isActiveTrip
     → useTripIntelligence → GET /locations/{lat,lon}/intelligence [VERIFIED]
     → TripWorkspacePanel + IntelligenceSidebar
```

Stage-by-stage verdicts (A–V from the audit brief):

| Stage | Verdict | Evidence |
|---|---|---|
| A New conversation | PASS | Clean entry, no workspace shown |
| B Initial trip message | PASS | `contextComplete: true` in one turn |
| C Destination extraction/geocoding | PASS | Lisbon/Kerala/Goa/Bali resolved correctly |
| D Date extraction | PASS | "September 22 to September 25" → `2026-09-22`/`2026-09-25` |
| E TripContext create/update | PASS | Persisted keys incl. `travelStyle`, `pace` |
| F Weather retrieval | PASS | 4 readings, varied, `cacheStatus: miss` |
| G Normalization | PASS | Conditions/temps/precip normalized |
| H Intelligence calc | PASS | Deterministic, config-driven |
| I Best day | PASS | `bestDays: ['2026-09-22']` |
| J Watch-out day | PASS | `worstDays: ['2026-09-25']` |
| K Daily intelligence | PASS | Per-day risk/advisory/activities |
| L Suitability | PASS | `70` matched UI exactly |
| M Confidence | PASS | `0.5475` → "Low confidence" |
| N Place discovery | PARTIAL | External-dependent, see §9 |
| O Packing | PASS | `['light cottons','sunscreen']` |
| P LLM response generation | PASS | 83–433 chars, concise |
| Q Persistence | PASS | 20 messages + places metadata |
| R Follow-up | PASS | Context retained, no re-asking |
| S Context modification | PASS | `pace: relaxed`, `travelStyle: family` |
| T Destination/date change | PARTIAL | Dates PASS; ambiguous destination → ISSUE-1 |
| U History | PASS | Rolling 3 shown, 10 retained server-side |
| V Intelligence Layer | PARTIAL | Persistent except under ISSUE-1 |

---

## 4. Frontend audit

**Genuinely dynamic — no hardcoded data found in the chat feature.** A repository-wide search for hardcoded destinations, conversations, places, scores and dates returned only: test fixtures (`active-trip.test.ts`), documentation examples in comments, and input placeholders (`placeholder="Goa"` in the unrelated `/plan` picker). No mock arrays, no seeded trips, no demo fallback data, no `src/mocks` directory.

**Network-verified.** A cold load of a conversation issued exactly three API calls — `GET /conversations/{id}`, `GET /conversations`, `GET /locations/10.8505,76.2711/intelligence` — all `200`, no interception. Rendered score `53` and rendered place `Al-bawadi` both trace to those payloads.

**Derived locally (legitimately):** day-state labels (`Best day`/`Watch-out`/`Take care`) are projections of `bestDays`/`worstDays` membership and `travelAdvisory`; the follow-up chips are derived from `intent` + `contextComplete` + `places.length`. Neither invents a fact.

**Ignored backend fields:** `destinationCandidates` is consumed only as a suppression signal (its contents are never rendered) — this is a deliberate product decision, not a defect. `missingEssentials` is stored but no longer rendered.

**Cache behaviour:** `useTripIntelligence` is keyed on `{locationId, start, end}`, so date and destination changes produce a new key and refetch — verified live (Sep 18–21 → Sep 22–25 recomputed). `latestPlaces` is scoped by trip identity, so a previous destination's places cannot leak into a new trip.

**Stale documentation (not a bug):** `PlannerPage.tsx:23` says "⚠️ Geocoding is mocked. Only `data/planner.mock.ts` changes when the real provider lands." That file does not exist; `DestinationPicker` uses the real `useGeocoding` hook against Open-Meteo. The comment is stale, the behaviour is real.

---

## 5. Backend audit

Clean layering enforced by `import-linter` (2 contracts, 0 broken). 508 tests pass, 19 skipped (Docker unavailable). `ruff` and `mypy` clean across 96 source files.

Error handling is consistently "degrade, don't fail": places unavailability is caught and logged (`places_unavailable`) rather than failing the turn; LLM failure falls back to a deterministic template; `422` is suppressed in favour of `400 VALIDATION_ERROR`.

One observation: `PlacesBackedAttractionProvider` logs the underlying exception into `extra={"error": ...}`, which the console log format does not render — so the *reason* places failed is invisible in logs. Only the bare string `places_unavailable` appears. This materially slowed root-causing during this audit.

---

## 6. LLM / Groq audit

**Configuration verified live:** base URL `https://api.groq.com/openai/v1`, model `openai/gpt-oss-20b`, key valid, timeout 30s, max output 3000 tokens. Response carries `finish_reason: stop` and a separate `reasoning` field; `LlmClient` correctly reads `content` only and rejects `finish_reason == "length"` and non-string content.

**Ten-turn live scenario matrix** (single Lisbon conversation):

| Turn | Intent | Complete | Dest | Dates | Places | LLM | Chars | Secs |
|---|---|---|---|---|---|---|---|---|
| Initial Lisbon trip | `trip_planning` | true | Lisbon, Portugal | 09-22..09-25 | 3 | true | 266 | 8.6 |
| Which day is best? | `itinerary_request` | true | Lisbon | unchanged | 0 | true | 83 | 75.0 |
| What if it rains? | `weather_question` | true | Lisbon | unchanged | 3 | true | 110 | 33.0 |
| What places can I visit? | `itinerary_request` | true | Lisbon | unchanged | 3 | true | 156 | 5.8 |
| What should I pack? | `packing_request` | true | Lisbon | unchanged | 0 | true | 86 | 1.6 |
| Day-by-day itinerary | `itinerary_request` | true | Lisbon | unchanged | 0 | true | 119 | 73.3 |
| Good for photography? | `recommendation_request` | true | Lisbon | unchanged | 3 | true | 192 | 8.0 |
| Keep it relaxed, parents | `itinerary_request` | true | Lisbon | unchanged | 3 | true | 433 | 6.6 |
| Change dates | `itinerary_request` | true | Lisbon | **09-24..09-27** | 0 | true | 141 | 81.3 |
| Paris instead | `trip_planning` | **false** | **null** | 09-24..09-27 | 0 | false | 236 | 2.2 |

**Conclusions.** Extraction is correct and reliable; year-less dates resolve (the prompt supplies today's date); context is retained across all follow-ups without re-asking; `travelStyle: family` and `pace: relaxed` were extracted from "Keep it relaxed, I'm travelling with my parents"; the date change was applied correctly. Responses are concise (83–433 chars) and grounded. Output is **not** verbose — the earlier verbosity problem is resolved.

**Two LLM-layer issues:** intent misclassification (ISSUE-5) and latency variance driven by the places call, not by Groq (ISSUE-2).

---

## 7. Weather-provider audit

`GET /providers/health` reports all four as `available`. This is misleading. `health.py:55` documents the mechanism: *"No record, or an expired one, reads as available."* Three providers share an identical `lastCheckedAt` of `15:55:14` while only `open_meteo` shows a fresh timestamp — i.e. only `open_meteo` has actually been exercised. `available` here means "no recorded failure", not "verified reachable".

**Real data confirmed.** `GET /weather/raw` for Lisbon returned four distinct readings with varied conditions (`clear`, `cloudy`), varied temperatures (17.0–30.2 °C) and varied precipitation (0.0, 0.12, 0.06). Not defaulted, not static, not fabricated. `cacheStatus: miss`, `degraded: false`.

`precipitationMm: 0.0` and `humidity: null` throughout — correct, since Open-Meteo's daily endpoint does not supply them and the schema marks them nullable.

**Fallback chain is untested in production.** Because `open_meteo` has not failed, `openweather` and `weatherapi` have never served a request. Their keys are configured but unverified end-to-end. `meteostat` has an empty key (`METEOSTAT_API_KEY=`) and is the historical-only provider, so it is inert.

**Verdict: weather data is REAL.**

---

## 8. Geocoding audit

| Destination | Result | Notes |
|---|---|---|
| Goa | `Goa, India` (15.2993, 74.1240) | Curated alias |
| Kerala | `Kerala, India` (10.8505, 76.2711) | Curated alias |
| Lisbon | `Lisbon, Portugal` (38.7223, −9.1393) | Resolved after disambiguation |
| Bali | resolved | 5 candidates offered on first mention |
| Paris | **ambiguous** — 5 candidates | Triggers ISSUE-1 |

Ambiguity detection works as designed (country/country-code diversity check) and the clarification reply lists real candidates. `tripContext.destination.latitude/longitude` format at 4 dp matches what `/locations/{id}/intelligence` expects, so no translation layer is needed — confirmed by the working intelligence calls.

No incorrect geographic resolution was observed in this audit.

---

## 9. Places / Overpass audit

This was the most-suspected area. The pipeline is **correct**; the failures are external and data-driven.

**Per-destination live results, default categories (`landmark`, `beach`, `museum`, `restaurant`):**

| Destination | Result | Time |
|---|---|---|
| Goa | 39 places | 9.8s |
| Lisbon | 34 places | 22.5s |
| Paris | `PlacesUnavailableError` (timeout) | 73.6s |
| Kerala | 34 places | 3.2s |
| Bali | 36 places | 14.9s |

**Same destinations, interest-derived categories, minutes later:**

| Case | Result | Time |
|---|---|---|
| Goa `beach`+`photography` | **0** | 9.2s |
| Lisbon `museum`+`food` | `PlacesUnavailableError` | 71.3s |
| Paris `museum`+`food` | **40 places** | 13.2s |

Paris failed in run 1 and succeeded in run 2; Lisbon did the reverse. **The results are non-deterministic across runs with identical inputs** — conclusive evidence of external load, not a coordinate, query or tag defect.

**Goa's zero is real OSM sparsity, proven separately.** Issuing the adapter's exact query shape (`nwr`, radius 15 km, `natural=beach` + `tourism=viewpoint`) returned `HTTP 200` with **1 raw element, 0 of which carried a `name` tag**. `_to_place` drops unnamed elements by design ("recommending an unnamed place would be worse than recommending nothing"), so 0 places is the correct output for that data. Goa's beaches are mapped in OSM predominantly as unnamed ways/areas.

**The mirror is dead.** Measured independently with an identical small query:

```
primary    HTTP 200 bytes=3642 in 1.1s
mirror     ERR ReadTimeout after 40.5s
```

Backend logs show `overpass_host_failed` appearing **twice per failure**, i.e. both hosts fail together. The mirror therefore never rescues a request; it only adds up to ~20s before the error surfaces. This is the direct cause of the 73–81s turns in §6.

**Observed upstream statuses:** `200`, `429 Too Many Requests`, `504 Gateway Timeout`.

**Frontend retention is correct.** Places persist in message metadata in the exact wire shape (`name`, `type`, `latitude`, `longitude`, `address`, `weatherSuitability`, `reason`), survive a browser refresh, and are re-read on thread restore — verified: 6 place rows rendered on a cold load of the Kerala conversation, and 5 messages in the Lisbon conversation carried persisted places.

**Verdict: places are EXTERNAL-DEPENDENT, not broken.**

---

## 10. Intelligence-engine audit

Traced for Lisbon 2026-09-22..25:

```
score: 70 | risk: moderate | confidence: 0.5475
best: ['2026-09-22'] | worst: ['2026-09-25']
packing: ['light cottons', 'sunscreen']
  09-22 clear    proceed  low       {outdoor:80, beach:70, museum:60}
  09-23 cloudy   proceed  low       {outdoor:80, beach:70, museum:60}
  09-24 cloudy   proceed  low       {outdoor:80, beach:70, museum:60}
  09-25 clear    caution  moderate  {outdoor:65, beach:80, museum:65}
```

Deterministic and config-driven (`2026.07`): activity bases 80/70/60 with penalties/bonuses per triggered risk type; `bestDays`/`worstDays` from `(risk_order, -mean_activity, date)`; confidence from horizon/agreement/completeness weights (0.4/0.2/0.4). Agreement is effectively fixed at 0.8 because only one provider serves — so confidence is systematically capped below what a multi-provider deployment would produce. That is a correct reflection of reality, not a bug.

**UI correspondence is exact.** The values above rendered as "70 / 100, Moderate risk, Low confidence, Best day Sep 22, Watch-out Sep 25" — confirmed by direct comparison against the rendered DOM.

---

## 11. Persistence / state audit

`GET /conversations/{id}` after a 20-message conversation returned: 20 messages, `tripContext` with `startDate`/`endDate`/`interests`/`travelStyle`/`pace`/`destinationQuery`, and 5 assistant messages carrying persisted `places`.

- Survives browser refresh: **yes** (verified — full workspace restored on cold load).
- Survives conversation switching: **yes** (`key`-based remount, fresh fetch).
- Rolling history window: display-only — rail showed **3** while `GET /conversations` returned **10**. Nothing is deleted server-side.

**One anomaly, tied to ISSUE-1:** after the unresolved Paris turn, the persisted `tripContext` contains `destinationQuery` but **no `destination`** — dates, interests, style and pace all survive. The trip is left in a permanently half-resolved state until the user disambiguates.

---

## 12. Frontend/backend contract audit

`frontend/openapi.json` is **byte-identical to the live runtime schema** (verified by generating and diffing). Generated `schema.d.ts` types are bound to hand-written domain types via `contract.ts`, so upstream drift becomes a compile error.

`ChatResponse` — required: `conversationId`, `response`, `contextComplete`, `missingEssentials`, `tripContext`, `intent`, `llmGenerated`; optional with defaults: `places`, `destinationCandidates`. The frontend correctly treats the latter two as possibly-absent.

Naming is consistently camelCase on the wire, including inside the open `tripContext` dict (hand-camelCased in `routers/conversation.py`). No snake_case leakage found — except `missingEssentials` **values**, which are snake_case (`start_date`, `end_date`); the frontend types model this correctly.

**No contract mismatches found.**

---

## 13. Static / mock-data audit

| Item | Location | Classification |
|---|---|---|
| `PROMPTS` example strings | `EmptyConversation.tsx` | Intentional UI affordance; deliberately contains **no** place names |
| `placeholder="Goa"` | `DestinationPicker.tsx:105` | Input placeholder, `/plan` route only |
| "Goa, India" in comments | `format.ts`, `location.ts`, `geocoding.ts` | Documentation |
| `GOA`/`BALI`/`Baga Beach` | `active-trip.test.ts` | Test fixtures |
| "Geocoding is mocked" comment | `PlannerPage.tsx:23` | **Stale documentation** — file referenced does not exist; behaviour is real |

**Nothing in the product path fabricates data or masks a backend failure.** Every empty state observed corresponded to a genuinely empty backend response.

---

## 14. Test-coverage audit

508 backend tests pass across 37 files; 17 frontend tests (vitest). 19 integration tests skip without Docker.

| Area | Coverage |
|---|---|
| Orchestrator logic, intents, extraction fallback | Unit — strong |
| Overpass adapter incl. host fallback | Unit (respx) — good |
| Intelligence rules/scoring | Unit — strong |
| API contract/envelope/validation | Integration — strong |
| Active-trip state, rolling history, place retention | Unit (frontend) — good |
| **Live LLM behaviour** | **None** — all LLM tests use fakes |
| **Real weather providers** | **None** — all mocked |
| **Real Overpass** | **None** — all respx |
| **Full `/chat` against real services** | **None** |
| **Frontend↔backend integration** | **None** — no component/E2E tests |
| **Browser behaviour** | **None** — manual only |

The gap that matters: **every failure found in this audit lives in the untested band.** ISSUE-1 in particular would be caught by a single component test asserting the workspace survives an ambiguous destination change.

---

## 15. Real E2E test matrix

| # | Scenario | Backend | Provider | API | Frontend | Verdict |
|---|---|---|---|---|---|---|
| A | Goa initial trip | context complete | Overpass 39 / 0 by category | 200 | workspace renders | **PASS** |
| B | Lisbon + places | complete | 34 places | 200, `places:3` | 6 rows in layer | **PASS** |
| C | Paris trip | ambiguous → clarify | n/a | 200 | candidates as prose | **PASS** (by design) |
| D | Kerala trip | complete, score 53 | 3 places | 200 | 6 rows, 4 days | **PASS** |
| E | Follow-ups ×4 | context retained | mixed | 200 | layer persists | **PASS** |
| F | Packing | `packing_request` | n/a | 200 | packing visible | **PASS** |
| G | Place discovery | `recommendation_request` | real names | 200 | rendered | **PASS** |
| H | Date modification | 09-22..25 → 09-24..27 | refetched | 200 | strip recomputed | **PASS** |
| I | Destination modification | destination **cleared** | n/a | 200 | **workspace vanishes** | **FAIL — ISSUE-1** |
| J | Relaxed/parents | `pace`/`travelStyle` set | n/a | 200 | persists | **PASS** |
| K | Browser refresh | thread restored | places from metadata | 200 | full workspace | **PASS** |
| L | Reopen conversation | restored | persisted places | 200 | renders | **PASS** |

Responsive check (Kerala conversation, real data at every size):

| Width | Overflow | Outlook | Places | Console errors |
|---|---|---|---|---|
| 390 | none | yes | 6 | 0 |
| 768 | none | yes | 6 | 0 |
| 1280 | none | yes | 6 | 0 |
| 1600 | none | yes | 6 | 0 |

---

## 16. Issue table

| ID | Issue | Category | Severity |
|---|---|---|---|
| ISSUE-1 | Ambiguous destination change destroys the active-trip workspace | A — Frontend bug (backend behaviour is intentional) | **HIGH** |
| ISSUE-2 | Dead Overpass mirror adds ~20s to failing turns (73–81s observed) | F — Configuration | **HIGH** |
| ISSUE-3 | `/providers/health` reports unprobed providers as `available` | H — Product/UX behaviour | **MEDIUM** |
| ISSUE-4 | `places_unavailable` log hides the actual error | B — Backend (observability) | **MEDIUM** |
| ISSUE-5 | "Which day is best?" classified as `itinerary_request` | D — LLM/prompt | **LOW** |
| ISSUE-6 | Stale "Geocoding is mocked" comment | G — Documentation | **LOW** |
| ISSUE-7 | Weather fallback chain never exercised in production | G — Verification gap | **MEDIUM** |
| ISSUE-8 | Goa returns 0 places for beach/photography | J — Expected limitation | **LOW** |
| ISSUE-9 | No live-service or frontend integration tests | G — Test gap | **MEDIUM** |

---

## 17. Detailed findings

### ISSUE-1 — Ambiguous destination change destroys the active-trip workspace

- **Observed:** After nine successful turns on an established Lisbon trip, "Let's go to Paris instead." returns a disambiguation question. The conversation still shows 21 messages, but Trip Intelligence, the sidebar, the day strip, places, packing and the trip identity header all disappear. Cold-loading the conversation URL reproduces it exactly: `outlook:false, layer:false, placeRows:0, days:0, tripHeader:false, msgCount:21`.
- **Expected:** The previous trip's intelligence should remain until the new destination resolves, or the UI should explicitly show a "resolving destination" state — not silently collapse.
- **Where:** `chat_orchestrator.py:671-677` (clears `destination` on ambiguity, by design) + `active-trip.ts` `tripState()` (requires `trip.destination`) + `ChatPage.tsx` (`activeTrip` gates header, workspace and sidebar).
- **Evidence:** Persisted `tripContext` keys after the turn: `['destinationQuery','endDate','interests','pace','startDate','travelStyle']` — `destination` absent. Browser state captured above.
- **Root cause:** The backend intentionally clears the resolved destination so the next turn re-resolves. The frontend treats "no destination" as "no trip", conflating *transiently unresolved* with *never established*.
- **Severity:** HIGH — core workflow, and the data loss is visual only (everything is still in the database), which makes it feel worse than it is.
- **Recommended fix:** Frontend-side. Retain the last *resolved* trip identity for workspace purposes while a disambiguation is pending. Do not change the backend clearing behaviour, which is correct.
- **Dependencies:** None.
- **Confidence:** High — reproduced deterministically in the browser and confirmed in persisted state.

### ISSUE-2 — Dead Overpass mirror inflates latency

- **Observed:** Chat turns of 75.0s, 73.3s and 81.3s. Independent probe: primary `200` in 1.1s, mirror `ReadTimeout` after 40.5s. Logs show `overpass_host_failed` twice per failure.
- **Expected:** A fallback host should reduce failure rate, not add tens of seconds.
- **Where:** `overpass.py` `_INTERPRETER_URLS`, with `_CLIENT_TIMEOUT_SECONDS = 20.0` applied per host.
- **Root cause:** `overpass.kumi.systems` is unreachable from this environment. Every primary failure now costs primary-timeout + mirror-timeout before surfacing.
- **Severity:** HIGH — worst observed turn 81s against a 60s frontend budget, so some turns can exceed the client timeout.
- **Recommended fix:** Either remove the mirror, replace it with a verified-reachable instance, or make the fallback conditional on a fast health probe. Configuration decision, not a code-structure problem.
- **Confidence:** High — measured directly.

### ISSUE-3 — `/providers/health` overstates availability

- **Observed:** All four providers `available`; three share `lastCheckedAt: 15:55:14` while only `open_meteo` is current.
- **Root cause:** Passive health cache — `health.py:55`: *"No record, or an expired one, reads as available."*
- **Severity:** MEDIUM — an operator would read this as "all providers verified", which is false.
- **Recommended fix:** Distinguish `unknown`/`unprobed` from `available`, or probe actively. **Note:** changing this alters an API contract and should be a deliberate decision.
- **Confidence:** High.

### ISSUE-4 — Places failure reason is invisible in logs

- **Observed:** Only the bare token `places_unavailable` appears; the exception message is passed via `extra={"error": ...}` which the console renderer drops.
- **Severity:** MEDIUM — this directly slowed this audit; in production it would make places incidents near-undiagnosable.
- **Where:** `places_provider.py:66`.
- **Confidence:** High.

### ISSUE-5 — Intent misclassification

- **Observed:** "Which day is best?" → `itinerary_request` (expected `weather_question` or a best-day intent); "What places can I visit?" → `itinerary_request` (expected `recommendation_request`).
- **Impact:** Limited — the response content was still correct, and follow-up chips are mostly unaffected. But `itinerary_request` skips the places fetch, which is why `places: 0` appeared on those turns despite an established trip.
- **Severity:** LOW (correctness) but it is the mechanism behind the visible places oscillation.
- **Confidence:** High.

### ISSUE-8 — Goa places (expected limitation, not a bug)

Overpass returned `200` with 1 unnamed element for Goa's beach/viewpoint tags. The unnamed-element filter is deliberate and correct. This is OSM data density, not an application defect. Default categories at the same coordinates returned 39 places, so Goa is not globally empty.

---

## 18. Root-cause classification summary

| Category | Issues |
|---|---|
| A Frontend bug | ISSUE-1 |
| B Backend bug | ISSUE-4 |
| C API contract mismatch | *none found* |
| D LLM/prompt | ISSUE-5 |
| E External provider reliability | Overpass `429`/`504`; dead mirror host |
| F Configuration/environment | ISSUE-2 |
| G Test/verification gap | ISSUE-6, ISSUE-7, ISSUE-9 |
| H Product/UX behaviour | ISSUE-3 |
| I Missing backend capability | *none found* |
| J Expected limitation | ISSUE-8 |

---

## 19. Recommended fix order

1. **ISSUE-1** — restore workspace persistence through destination disambiguation. Highest user-visible impact; frontend-only; low risk.
2. **ISSUE-2** — resolve the mirror. Removes up to ~40s from failing turns; configuration-only.
3. **ISSUE-4** — surface the places error message. Cheap; unblocks all future places diagnosis.
4. **ISSUE-5** — intent classification for day/places questions. Restores consistent places fetching.
5. **ISSUE-9** — add a component test for the active-trip lifecycle and a live smoke test.
6. **ISSUE-3** — decide the health-reporting semantics (contract change; needs a product call).
7. **ISSUE-6** — delete the stale comment.

---

## 20. Items that should NOT be changed

- **The backend clearing `destination` on ambiguity.** Correct and deliberate; fix ISSUE-1 in the frontend.
- **The drop-unnamed-places filter.** Recommending unnamed places would be worse than recommending none.
- **The `nwr` query shape and 4 dp `location_id` format.** Both verified correct.
- **Persisting places in message metadata.** This is what makes refresh and thread-restore work.
- **The deterministic rule engine and its config.** Values verified; UI matches exactly.
- **The response-generation prompt.** Output is now concise and grounded; further tightening risks stripping useful reasoning.
- **The rolling history window.** Display-only, backend retains everything — working as specified.
- **The `contract.ts` type-binding layer.** It is what keeps the contract honest.

---

## 21. External limitations (not application bugs)

- **Overpass public instances** rate-limit (`429`) and shed load (`504`) unpredictably. Identical queries succeed and fail minutes apart.
- **`overpass.kumi.systems`** is unreachable from this environment.
- **OSM data density** varies by region and tag; Goa's beaches are largely unnamed ways.
- **Single weather provider in practice** caps `travelConfidence` agreement at 0.8.
- **Groq latency** is not the bottleneck — measured 0.5s on a trivial call; chat latency is dominated by Overpass.

---

## 22. Final conclusions

1. **Is the frontend genuinely connected to the backend?** Yes. Network-verified: three real API calls on cold load, no mocks, rendered values traceable to payloads.
2. **Which frontend features are genuinely dynamic?** All of them in the chat product — trip identity, outlook, suitability, confidence, best/watch-out, day strip, day detail, places, packing, trip context, history.
3. **Which are static or misleading?** None in the product path. Only a stale comment (ISSUE-6) and input placeholders.
4. **Is the LLM understanding and responding correctly?** Yes. Ten live turns: correct extraction, retained context, correct date and pace/style updates, concise grounded replies (83–433 chars). One intent misclassification.
5. **Is weather data reaching the intelligence engine?** Yes — real varied forecast data, `cacheStatus: miss`, `degraded: false`.
6. **Why are places missing (when they are)?** Three distinct causes: Overpass `429`/`504` under load; genuine OSM sparsity at specific coordinate/tag combinations (Goa beaches); and `itinerary_request` misclassification skipping the fetch.
7. **Is the place problem application-side or external?** **Predominantly external.** The one application-side contributor is ISSUE-5.
8. **Is trip intelligence computed correctly?** Yes — deterministic, config-driven, verified against the engine's own rules.
9. **Is the Intelligence Layer receiving real data?** Yes, with the ISSUE-1 exception where it receives nothing because the frontend has discarded the trip.
10. **Are there API contract mismatches?** No. OpenAPI is byte-identical to runtime.
11. **Top 5 root causes:** (1) frontend conflates unresolved-destination with no-trip; (2) dead mirror host; (3) Overpass external instability; (4) intent misclassification skipping places; (5) no live-service or integration test coverage over any of the above.
12. **Fix first:** ISSUE-1, then ISSUE-2.
13. **Do not touch:** §20.
14. **True system health:** **Good.** The architecture is sound, the data is real, the contract is honest, and the core journey works end to end. One HIGH-severity frontend bug and one self-inflicted latency regression stand between this and a reliably production-quality experience. Nothing is faked; nothing is masking a backend failure.

---

*Audit performed without modifying any production code, prompt, schema, contract, configuration or provider logic.*
