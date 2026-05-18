# ParkSmart Frontend (Plan 4) — Design Spec

**Date:** 2026-05-17 · **Revision:** 2026-05-18 — marker/predict fan-out ~N; **`usePredictions` passes `car_park_id` into `/api/predict?location=`** (stable, avoids `&` / fuzzy errors)
**Author:** solo developer
**Status:** approved for implementation
**Builds on:** `docs/superpowers/specs/2026-05-11-parksmart-design.md` (master spec)

---

## 1. Purpose

Plan 4 delivers the ParkSmart user interface — the only layer a resident or visitor
actually touches. The backend (Plans 1–3) is feature-complete: a typed REST + SSE API
backed by live TfNSW data, an XGBoost predictor, KML-derived zone rules, and an LLM
assistant. This document covers the React single-page app that consumes it.

The three user-success criteria from the master spec (§3) are the acceptance bar:

1. **Recommendation** — ask "where should I park near Westfield at 6pm Friday?" and get
   a specific named car park with occupancy %, confidence, and walking context.
2. **Restrictions** — ask "what are the rules on Victoria Avenue?" and get a plain-English
   answer accurate enough to avoid a fine.
3. **Live map** — see one marker per `/api/occupancy` row (CBD estimates + TfNSW live sites) auto-refreshing, with live data visually distinct from estimated data.

---

## 2. Decisions locked in this design

These resolve the open questions for the frontend. Where a decision changes the master
spec, it is called out.

| Area | Decision | Note |
|---|---|---|
| Primary form factor | **Mobile-first**, with a desktop re-flow | **Overrides** master spec §4 ("single page: full-bleed map + 380px right chat drawer" was desktop-only). The 380px drawer becomes the *desktop* presentation; mobile uses a bottom sheet. |
| Prediction UI | **Time scrubber on the map** + a typed datetime input | A slider re-colours all markers for a chosen hour; a tappable time chip opens a text/`datetime-local` input for exact entry. Both bind to one shared target-time state. |
| Zone restrictions UI | **Street search panel** + the chat assistant | A search field with street autocomplete returns per-side rule cards. The assistant answers the same questions via its existing `get_zone_restrictions` tool — no extra cost. |
| Frontend testing | **Minimal / manual** | No frontend test suite. Correctness rests on TypeScript, a typed API client mirroring the backend models, and manual QA against the 3 success criteria. The backend's automated tests guard the API. |
| State management | React Context for chat; local React state for the map | Per master spec §4 — no state library. |
| Stack | React 18 + Vite + TypeScript + Tailwind CSS + Leaflet (`react-leaflet`) | Per master spec. |

---

## 3. Layout

One set of components. A single CSS breakpoint (Tailwind `md:`) re-flows them between
mobile and desktop. No duplicated logic, no separate mobile build.

### Mobile (primary)

The map fills the screen. Everything else floats over it or slides up from the bottom:

- **Search field** — pinned top, full width. Street parking rules.
- **Time scrubber** — below the search field: a slider plus a tappable time chip
  (chip shows `NOW` or e.g. `FRI 6PM`; tapping it opens an exact-time input).
- **Bottom sheet** — collapsed to a pill ("Ask ParkSmart…") by default. Drag up for the
  full chat assistant. When a marker is tapped, the sheet shows that car park's detail
  card instead of chat. The sheet shows chat **or** a detail card, never both.
- **Map** — fills everything behind.

### Desktop (re-flow at `md:` and up)

- **Right drawer (380px, always visible)** — the chat assistant. Same `AssistantPanel`
  component as the mobile bottom sheet, docked instead of collapsible.
- **Car-park detail** — a Leaflet popup anchored to the marker, *not* the drawer. Desktop
  has room for chat and a detail popup at once; mobile does not.
- **Search field + time scrubber** — float on the map (top-left and bottom-center).
- **Zone rules result** — a card panel that slides down under the search field, over the map.

The responsive difference is confined to two components: `AssistantPanel` (bottom sheet
vs. side drawer) and `CarParkDetail` (sheet content vs. Leaflet popup).

---

## 4. Component architecture

```
App
├── MapView                 Leaflet map, fitted to Chatswood CBD bounds
│   ├── CarParkMarker × N     pin colour = occupancy %; pin style = provenance
│   └── CarParkDetail        desktop → Leaflet popup; mobile → bottom-sheet content
├── SearchField             street autocomplete → zone lookup
│   └── ZoneRulesCard        per-side rule cards
├── TimeScrubber            slider + typed datetime input; owns the shared target-time
└── AssistantPanel          desktop → 380px right drawer; mobile → bottom sheet
    ├── MessageList
    │   ├── MessageBubble
    │   └── ToolCallBadge
    └── MessageInput
```

### Hooks

| Hook | Responsibility |
|---|---|
| `useOccupancy()` | Polls `GET /api/occupancy` every 5 minutes → one snapshot per seeded car park (`N ≥ 40` TfNSW + CBD sim garages). |
| `usePredictions(targetTime)` | When `viewTime` is set, fans out `/api/predict` **once per occupancy row**, passing **`car_park_id` as the `location` query** (stable backend key; avoids `Park&Ride` / `&` encoding and loose name fuzzy match). |
| `useChat()` | SSE state machine over `POST /api/chat`. |
| `useZones(street)` | `GET /api/zones?street=` → per-side rule segments. |

### State model — single `viewTime`

The map is either showing *now* or a chosen future hour. Rather than two hooks plus a
mode toggle, one piece of state drives it:

- `viewTime === null` → **live mode**: markers read `useOccupancy`.
- `viewTime` is a `Date` → **predicted mode**: markers read `usePredictions(viewTime)`.

`TimeScrubber` owns `viewTime`; `MapView` reads it. Both modes produce one uniform shape:

```ts
type MarkerData = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  pct: number;                       // 0..1 occupancy
  source: "tfnsw" | "simulated";
  mode: "live" | "predicted";
  confidence?: number;               // present only when mode === "predicted"
  modelVersion?: string;             // "xgboost-v1" | "simulator-v1"
};
```

`CarParkMarker` renders `MarkerData` without branching on live-vs-predicted. Dragging the
scrubber back to "Now" sets `viewTime = null` and returns to live polling.

Chat state lives in `ChatContext`. Map state (`viewTime`, selected marker) is local to `App`.

---

## 5. API integration

`types.ts` mirrors the backend Pydantic models exactly. `api.ts` wraps each endpoint in a
typed fetch. `vite.config.ts` proxies `/api` → `http://localhost:8000`.

| Trigger | Request | Response |
|---|---|---|
| Mount + 5-min timer | `GET /api/occupancy` | `OccupancyResponse[]` (**N** entries) |
| Scrubber set to a future time | `GET /api/predict?location=<car_park_id>&target_datetime=` × **N** | `PredictionResult` per park |

`location` may still be human-readable names (e.g. LLM/chat); batch map calls should use **`car_park_id`** per backend spec §8 troubleshooting.
| Street selected | `GET /api/zones?street=` | `ZoneResponse` |
| Autocomplete list | `GET /api/zones/streets` | `string[]` (new — see §7) |
| Message sent | `POST /api/chat` | SSE stream |

### Prediction fan-out

`/api/predict` takes one `location` at a time. `usePredictions` issues **N parallel calls**
(`Promise.allSettled`, once per occupancy marker / car-park name). A rejected or
error-status park renders as "no prediction" for that marker; the rest of the map is
unaffected. No batch endpoint — Plan 4 stays frontend-only apart from §7.

### Chat / SSE

`/api/chat` is a **POST**, so the browser `EventSource` (GET-only) cannot be used.
`useChat` does a `fetch` with a `ReadableStream` reader, buffers the body, splits on
`\n\n`, and parses each `data:` payload as JSON. The backend emits four event types
(`app/services/llm_service.py`):

- `{"type":"text","content":str}` → append to the streaming assistant bubble
- `{"type":"tool_call","tool":str,"input":dict}` → render a `ToolCallBadge`
- `{"type":"tool_result","tool":str,"result":dict}` → kept internally, not shown raw
- `{"type":"done"}` → finalize the turn

The request body is `{message, history}`, where `history` is the prior
`{role, content}` pairs so the assistant keeps context.

---

## 6. Data transparency

The master spec (§14) treats this as a correctness requirement, not polish. Every car
park carries a badge the frontend must not omit.

| Data | `source` / `model_version` | Badge |
|---|---|---|
| Live occupancy (Gordon, Lindfield) | `source = "tfnsw"` | green **Live** |
| Estimated occupancy (5 CBD parks) | `source = "simulated"` | grey **Estimated** |
| ML prediction (TfNSW parks) | `model_version = "xgboost-v1"` | **Predicted · X% confidence** |
| Estimation-based prediction | `model_version = "simulator-v1"` | **Estimated · typical patterns** |
| Zone rules | — | **Source: Willoughby Council** |

Marker **colour** encodes occupancy; marker **style** encodes provenance — two
independent axes:

- Colour: green `pct < 0.70`, amber `0.70 ≤ pct < 0.90`, red `pct ≥ 0.90`.
- Style: solid pin = live (`tfnsw`), outlined pin = estimated (`simulated`).

`lib/occupancy.ts` holds the colour thresholds and the `OccupancyResponse` /
`PredictionResult` → `MarkerData` mapping, so the rule lives in exactly one place.

---

## 7. Backend addition

`SearchField` autocomplete needs the set of known streets. A static frontend list goes
stale whenever KML geocoding re-runs and resolves more streets. Plan 4 therefore adds one
small endpoint:

```
GET /api/zones/streets  →  ["Albert Avenue", "Victoria Avenue", ...]
```

Returns the distinct, non-null `parking_signs.street` values plus any streets present in
`seed_zones.json`, sorted. Implemented in `app/routers/zones.py` delegating to a
`zone_service.list_streets(db_path)` function (service layer stays FastAPI-free, per
project conventions). This is the only backend change in Plan 4.

---

## 8. Error and loading states

| Situation | Behaviour |
|---|---|
| `GET /api/occupancy` fails | Keep last good data, show a "data may be stale" note. If it never loaded, a map-level error toast with retry. |
| A `/api/predict` call returns 404/422 | That one marker shows "no prediction"; map stays usable. The scrubber clamps `viewTime` to `now … now+7d`, so `out_of_range` should not occur. |
| `GET /api/zones` returns 404 | `ZoneRulesCard` shows "No parking rules found for *X*". |
| Chat network error or stream interrupted | Error bubble with a retry button; any partial streamed text finalizes gracefully. |
| Initial load | Skeleton markers on the map; spinner in the assistant panel. |

---

## 9. Project structure

```
frontend/
├── package.json
├── vite.config.ts          proxy /api → http://localhost:8000
├── tailwind.config.js
├── tsconfig.json
├── index.html
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── api.ts               typed fetch wrappers
    ├── types.ts             mirror of backend Pydantic models
    ├── hooks/
    │   ├── useOccupancy.ts
    │   ├── usePredictions.ts
    │   ├── useChat.ts
    │   └── useZones.ts
    ├── context/
    │   └── ChatContext.tsx
    ├── components/
    │   ├── Map/
    │   │   ├── MapView.tsx
    │   │   ├── CarParkMarker.tsx
    │   │   └── CarParkDetail.tsx
    │   ├── Scrubber/
    │   │   └── TimeScrubber.tsx
    │   ├── Zones/
    │   │   ├── SearchField.tsx
    │   │   └── ZoneRulesCard.tsx
    │   └── Assistant/
    │       ├── AssistantPanel.tsx
    │       ├── MessageList.tsx
    │       ├── MessageBubble.tsx
    │       ├── ToolCallBadge.tsx
    │       └── MessageInput.tsx
    └── lib/
        └── occupancy.ts     colour thresholds, MarkerData mapping
```

Backend: one route added to `app/routers/zones.py`; one function added to
`app/services/zone_service.py`.

---

## 10. Build sequence

Each step is independently runnable against the live backend.

1. **Scaffold** — Vite + React + TS + Tailwind + Leaflet; `vite.config.ts` proxy;
   `types.ts` and `api.ts`.
2. **Live map** — `MapView` + `useOccupancy` + `CarParkMarker`; markers colour-coded and
   auto-refreshing every 5 minutes. Satisfies success criterion 3.
3. **Predicted mode** — `TimeScrubber` (slider + typed input) + `usePredictions` + the
   `viewTime` state model; markers re-colour for a chosen hour.
4. **Car-park detail** — `CarParkDetail` as a Leaflet popup (desktop) and bottom-sheet
   content (mobile).
5. **Zone search** — backend `GET /api/zones/streets`; `SearchField` + `useZones` +
   `ZoneRulesCard`. Satisfies success criterion 2 (non-chat path).
6. **Assistant** — `ChatContext` + `useChat` SSE state machine + `AssistantPanel`,
   `MessageList`, `MessageBubble`, `ToolCallBadge`, `MessageInput`. Satisfies
   success criterion 1.
7. **Responsive** — the `md:` breakpoint: bottom sheet ↔ right drawer, sheet detail ↔
   Leaflet popup.
8. **Manual QA** — walk the 3 success criteria on a narrow and a wide viewport;
   confirm every marker shows a Live/Estimated badge and predictions show confidence.

---

## 11. Out of scope for Plan 4

Per the master spec's future-phases list: user accounts, native app, push notifications,
multi-council data, payment/booking. Also deferred: a frontend test suite, a map layer of
individual zone signs (the search panel covers the zone feature for the MVP), and a batch
prediction endpoint (parallel fan-out proportional to occupancy list length remains acceptable until a batch API ships).
