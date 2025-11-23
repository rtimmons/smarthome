# Snapshot Service
Backend add-on that returns a fully shaped daily snapshot JSON for the `printer` UI to render (no client-side intelligence needed). Uses TypeScript + Fastify for speed, safety, and easy local development.

## Tech stack
- Node.js 20 (per repo `.nvmrc`), TypeScript, Fastify (or Express if preferred), pnpm.
- Runtime validation + OpenAPI from one source (e.g., Zod + zod-openapi).
- Testing: Vitest + Supertest, tsx for watch mode, msw-style mocks for outbound APIs.
- Tooling: ESLint + Prettier + type-check + coverage in CI; Husky/lint-staged optional.
- Config: dotenv for local, typed config loader, strict TS.

## Milestones
1) **Bootstrap + mock endpoint**  
   - Scaffold service with `Justfile` targets: `setup` (install deps), `dev` (fast reload server), `lint`, `test`, `fmt`, `typecheck`, `build`.  
   - Expose `GET /snapshot` serving a single mock JSON file (fixtures) that already matches the printer contract. `just dev` should bring this up locally.  
   - Add CI job (GitHub Actions) running lint/test/typecheck.
2) **Data contract + validation**  
   - Define `Snapshot` schema (Zod) and derive OpenAPI/JSON Schema; publish `/openapi.json`.  
   - Keep the printer dumb: snapshot includes all derived fields (today’s date, localized strings, computed highs/lows, week rows, etc.).  
   - Add contract tests that ensure fixture conforms to schema and is backward-compatible.
3) **Sources + adapters**  
   - Weather provider adapter (e.g., OpenWeather or Tomorrow.io) behind an interface; add caching + timeouts + fallback to mock.  
   - Calendar adapter (Google Calendar/Workspaces service account + timezone handling).  
   - Optional adapters: commute (Google/Apple/Here), health metrics, reminders/tasks.  
   - Use dependency injection to swap real vs mock in dev/test.
4) **Composition + business rules**  
   - Snapshot builder aggregates adapters, handles timezones, dedupes overlaps, clamps text lengths, and sets color/intensity hints (e.g., `status: "today"` → printer renders in red).  
   - Add feature flags for sections (weather/calendar/schedule/reminders/commute/habits/metrics).
5) **Operations**  
   - Structured logging, request IDs, healthcheck (`/healthz`), metrics-ready hook (Prom/StatsD).  
   - Configurable port/bind address; minimal runtime image (node:20-slim + pnpm prune).  
   - Add-on packaging: `addon.yaml`, container build, and hook into root `tools/addon_builder.py`.

## First success criteria (`just dev`)
- `just dev` runs Fastify in watch mode and serves `GET /snapshot` returning a static fixture from `fixtures/snapshot.json`.  
- Lint/test pass; `just test snapshot-service` (or equivalent) runs Vitest suite over the fixture and schema.  
- Printer add-on can hit `http://localhost:<port>/snapshot` and render without any extra logic.

## Proposed JSON shape (fixture example)
```json
{
  "generated_at": "2024-09-10T07:14:00-07:00",
  "timezone": "America/Los_Angeles",
  "today": { "iso_date": "2024-09-10", "weekday": "Tuesday", "label": "Tue Sep 10, 2024" },
  "weather": {
    "summary": "Mostly Cloudy",
    "temperature_now_f": 68,
    "temperature_high_f": 71,
    "temperature_low_f": 55,
    "feels_like_f": 67,
    "wind_mph": 6,
    "wind_direction": "NW",
    "chance_of_rain_pct": 10,
    "humidity_pct": 62,
    "aqi": 32,
    "uv_index": 5
  },
  "calendar_month": {
    "year": 2024,
    "month": 9,
    "weeks": [
      [{ "day": 8, "status": "past" }, { "day": 9, "status": "past" }, { "day": 10, "status": "today" }]
    ],
    "month_label": "September"
  },
  "schedule": [
    { "time": "08:30", "title": "Standup", "duration_minutes": 30, "location": "Zoom", "source": "work" },
    { "time": "10:00", "title": "Client Sync", "duration_minutes": 60, "location": "Room 2B", "source": "work" },
    { "time": "12:30", "title": "Lunch w/ Alex", "location": "Cafe Grin" },
    { "time": "15:00", "title": "Dentist", "duration_minutes": 45 },
    { "time": "19:00", "title": "Date Night" }
  ],
  "reminders": ["Water plants", "Ship return by 5pm"],
  "commute": {
    "legs": [
      { "label": "Home → Office", "duration_minutes": 22, "traffic": "light", "route": "101N" },
      { "label": "Office → Home", "duration_minutes": 28, "traffic": "moderate", "route": "280S", "notes": "after 6:15p" }
    ]
  },
  "habits": [
    { "label": "Hydrate x8", "checked": false },
    { "label": "Stretch", "checked": false },
    { "label": "Meds AM", "checked": false }
  ],
  "metrics": { "glucose_mg_dL": 96, "hydration_cups": 1 },
  "tips": ["Do 2h deep work before noon"]
}
```

Notes: `status: "today"` is what the printer uses to render the date in red; any future/past styling can follow the same pattern (`past`, `future`, `disabled`). Long strings should be truncated server-side to fit the receipt width.
