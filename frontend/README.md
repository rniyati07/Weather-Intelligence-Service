# Weather Intelligence Service — Frontend

A conversational AI travel assistant. The app opens directly into a
conversation (`/`, `/chat/:conversationId`) — there is no marketing homepage
in front of it. The original deterministic dashboard is retained as a
secondary, opt-in deep-dive (`/trip/:locationId`), reached from a Trip
Summary Card's "View full intelligence" action, alongside a manual `/plan`
flow for anyone who prefers a form.

Design source of truth: [`docs/06_Frontend_Design_Specification.md`](../docs/06_Frontend_Design_Specification.md) (Revision 2).
Contract source of truth: the backend's live `/openapi.json`, regenerated into
[`openapi.json`](openapi.json) / [`src/services/api/schema.d.ts`](src/services/api/schema.d.ts)
via `npm run generate:api` whenever the backend contract changes.

## Getting started

```bash
cd frontend
cp .env.example .env.local     # fill in API_KEY for the dev proxy
npm install
npm run dev                    # http://localhost:5173
```

| Script | Does |
|---|---|
| `npm run dev` | Vite dev server with the BFF proxy attached |
| `npm run build` | Typecheck, then production build |
| `npm run typecheck` | `tsc -b` only |
| `npm run lint` | ESLint (flat config, type-aware) |
| `npm run format` | Prettier, with Tailwind class sorting |
| `npm run verify` | typecheck + lint + format check — run before pushing |

## Constraints that shape the architecture

**The API key never reaches the browser.** The client calls a same-origin
`/api` path; a proxy running in Node attaches `X-API-Key`. In development that
proxy is [`vite.config.ts`](vite.config.ts); in production it needs a real BFF
(not yet built — see "Not yet built" below). The key is read from `API_KEY`,
deliberately *without* a `VITE_` prefix, so Vite refuses to inline it even if
someone references it by mistake. Verify with `grep -ri "x-api-key" dist/`
after a build — it must return nothing.

**Two narration paths, two failure contracts.** `POST .../intelligence/narrative`
(the deep-dive's AI Explanation card) is mandatory server-side, so an LLM
failure there returns `503 SERVICE_DEGRADED` rather than a `200` with a
fallback — fired in parallel with `GET /intelligence`, never awaited before
painting, confined to its own card on failure. Chat is the opposite: an LLM
failure inside `POST /conversations/chat` is absorbed server-side into a
normal `200` with a deterministic fallback (`llmGenerated: false`) — there is
no "AI unavailable" state to build for chat, and building one would wait on a
failure mode that can't reach the frontend.

**Geocoding happens in two places now.** Chat resolves a destination
server-side (free text in, a resolved `TripContext` out); `/plan`'s manual
flow still geocodes client-side, since the deep-dive's `/trip/:locationId`
only ever accepts a resolved `{lat},{lon}`. A chat-resolved destination's
`latitude`/`longitude` (4dp) already match that `locationId` format exactly —
see `TripSummaryCard`'s "View full intelligence" link for the one place this
matters.

**Chat is a single blocking request/response.** `POST /conversations/chat`
returns the complete reply in one call — there is no streaming to model a UI
around. `TypingIndicator` communicates "waiting for a reply", not "receiving
one token at a time".

## Structure

```
src/
├── app/            Composition root — providers, query client
├── routes/         Route table, router-level error boundary
├── features/       Domain modules. The bulk of the app.
│   └── chat/       The primary experience — ChatShell, MessageBubble,
│                   TripSummaryCard, ConversationHistoryPanel, …
├── components/
│   ├── ui/         Primitives. Zero domain knowledge.
│   ├── common/     Shared app-level pieces (Container, PageTitle, SearchInput)
│   ├── layout/     Shell — Navbar, Footer, MainLayout, PageContainer, Section…
│   ├── feedback/   EmptyState, ErrorState, LoadingSkeleton
│   ├── cards/      Domain card shells         (reserved)
│   ├── forms/      Form controls              (reserved)
│   └── weather/    Weather display primitives (reserved)
├── hooks/          Reusable behaviour. Bridges services → features.
├── services/       The only modules that know HTTP and localStorage exist
├── context/        React contexts (theme)
├── constants/      Routes, domain vocabulary, date limits, cache policy
├── types/          The API contract, hand-written from the spec
├── utils/          Pure formatting and lookup helpers
├── lib/            cn(), env, Framer Motion presets
└── styles/         tokens.css + globals.css — the only source of colour
```

### Import rules

These are what keep the graph from turning into a mesh:

- `components/ui` knows nothing about weather. If a primitive needs to know what
  a risk level is, it belongs in `components/cards` instead.
- A feature may import `components/`, `hooks/`, `lib/`, `utils/`, `constants/`
  and `types/` — **never another feature**. Shared logic is promoted to
  `components/` or `hooks/`.
- Only `services/api` knows HTTP. Components do not import it; hooks do.
- Only `services/storage` touches `localStorage`.
- Pages are composition only. Logic there belongs in a feature or a hook.

## Design tokens

Three layers, in [`src/styles/tokens.css`](src/styles/tokens.css):

1. **Primitives** — `--brand-500`, `--neutral-200`. Theme-independent. Never
   referenced by a component.
2. **Semantics** — `--background`, `--risk-high`, `--ai-surface`. Redefined per
   theme. The only layer a feature author thinks about.
3. **Utilities** — published to Tailwind by `@theme inline` in
   [`globals.css`](src/styles/globals.css) as `bg-surface`, `text-risk-high`, …

Dark ships as the default; light is authored in full under `:root` so enabling
it is a class toggle, not a project.

**Never hard-code a colour.** ESLint fails the build on a hex literal in a
`.ts`/`.tsx` file.

### Breakpoints

The FDS names four bands. Tailwind is mobile-first, so the unprefixed base *is*
the `sm` band and the prefixes line up one-to-one:

| FDS band | Range | Tailwind |
|---|---|---|
| `sm` | < 640 | *(no prefix)* |
| `md` | 640–1023 | `md:` |
| `lg` | 1024–1279 | `lg:` |
| `xl` | ≥ 1280 | `xl:` |

Tailwind's own `sm` and `2xl` are removed, so nothing can introduce a fifth band
the design does not define.

## Accessibility

Target is WCAG 2.1 AA. Built into the foundation rather than retrofitted:

- Every status chip requires an icon — colour is never the sole carrier of
  meaning.
- Risk colours are pre-verified for AA contrast and separability under
  deuteranopia and protanopia.
- Semantic landmarks and a skip link live in the shell, not per route.
- Modals and tooltips are Radix primitives, so focus trapping, `Escape`, focus
  restoration and keyboard operation come for free.
- All typography is in `rem`, so browser font-size settings are respected.
- `prefers-reduced-motion` is honoured in CSS *and* in the Framer Motion presets
  — CSS cannot reach the inline styles Framer Motion writes.

## Not yet built

| Missing | Notes |
|---|---|
| Production BFF | `vite.config.ts`'s dev/preview proxy is not a deployment target. Production needs a real Node adapter holding `X-API-Key`, same header-injection contract, client code unchanged. |
| Structured place data in `PlaceReferenceStrip`/`FollowUpSuggestions` | Populated correctly for any turn sent *this session* (`ChatResponse.places`), but a restored conversation (`GET /conversations/{id}`) carries no persisted place data — this is a backend limitation (FDS Revision 2 §7.3 `[BACKEND GAP]`), not a frontend gap. |
| Visible destination-disambiguation UI | `destinationCandidates` is read and typed end-to-end, but per the current approved scope the assistant's own prose (which lists the options) is the only UI — no clickable candidate buttons yet. |
| Component/E2E tests | `tests/` — none exist yet for either the chat or the dashboard surface. |
| Browser-driven responsive/a11y verification | Typecheck, lint, format and a production build are clean and verified; an actual multi-breakpoint, screen-reader pass has not been done in this environment. |
