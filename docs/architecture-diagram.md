# ParkSmart - Software Architecture

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         USER (Web Browser)                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
┌────────────────────────────────▼────────────────────────────────────────┐
│                      FRONTEND - React SPA                                │
│  ┌──────────────────────────┐      ┌──────────────────────────────┐    │
│  │   Leaflet Map Layer      │      │   Chat Drawer (380px)        │    │
│  │  • 7 car park markers    │      │  • Message list              │    │
│  │  • Color by occupancy %  │      │  • Input box                 │    │
│  │  • Live/Estimated badge  │      │  • Tool-call indicators      │    │
│  │  • Auto-refresh (5 min)  │      │  • SSE stream handling       │    │
│  └──────────────────────────┘      └──────────────────────────────┘    │
│                                                                           │
│  State Management: React Context (chat) + Local State (map)              │
└───────────────────┬──────────────────────────┬────────────────────────────┘
                    │ REST                     │ SSE (Server-Sent Events)
                    │ (polling)                │ (streaming)
┌───────────────────▼──────────────────────────▼────────────────────────────┐
│                     BACKEND - FastAPI Application                          │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                      API ROUTER LAYER                              │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────┐  │   │
│  │  │GET /api/     │  │GET /api/     │  │GET /api/     │  │POST  │  │   │
│  │  │occupancy     │  │zones         │  │predict       │  │/api/ │  │   │
│  │  │              │  │?street=...   │  │?location=... │  │chat  │  │   │
│  │  │List all      │  │              │  │&datetime=... │  │      │  │   │
│  │  │car parks     │  │Street rules  │  │              │  │SSE   │  │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └───┬──┘  │   │
│  └─────────┼──────────────────┼──────────────────┼──────────────┼─────┘   │
│            │                  │                  │              │         │
│  ┌─────────▼──────────────────▼──────────────────▼──────────────▼─────┐   │
│  │                      SERVICE LAYER (Pure Python)                   │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐   │   │
│  │  │ occupancy_      │  │ zone_           │  │ prediction_      │   │   │
│  │  │ service         │  │ service         │  │ service          │   │   │
│  │  │                 │  │                 │  │                  │   │   │
│  │  │• Merge real +   │  │• DB lookup      │  │• Route by source │   │   │
│  │  │  simulated      │  │• seed fallback  │  │• Sim (Plan 2)    │   │   │
│  │  │• Fuzzy matching │  │• Group by side  │  │• XGBoost (Plan3) │   │   │
│  │  │• Tool contract  │  │• Tool contract  │  │• Tool contract   │   │   │
│  │  └────────┬────────┘  └────────┬────────┘  └────────┬─────────┘   │   │
│  │           │                    │                     │             │   │
│  │           │      ┌─────────────▼─────────────────────▼────────┐    │   │
│  │           │      │        llm_service                          │    │   │
│  │           │      │  • AsyncAnthropic client                    │    │   │
│  │           │      │  • Tool dispatch (calls 3 services)         │    │   │
│  │           │      │  • 5-iteration loop cap                     │    │   │
│  │           │      │  • SSE generator                            │    │   │
│  │           │      └─────────────────────────────────────────────┘    │   │
│  │           │                                                         │   │
│  │           │      ┌──────────────────────────────────────────────┐  │   │
│  │           └─────▶│           simulator                          │  │   │
│  │                  │  • Deterministic pattern model               │  │   │
│  │                  │  • Cosine peak curve                         │  │   │
│  │                  │  • MD5-seeded noise                          │  │   │
│  │                  └──────────────────────────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
│                                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐   │
│  │                   BACKGROUND SCHEDULER (APScheduler)               │   │
│  │  ┌──────────────────────┐          ┌───────────────────────────┐  │   │
│  │  │ TfNSW Poll Job       │          │ Sim Refresh Job           │  │   │
│  │  │ • Every 5 minutes    │          │ • Every 1 hour            │  │   │
│  │  │ • Calls TfNSW API    │          │ • Generates sim snapshots │  │   │
│  │  │ • Upserts to DB      │          │ • Writes to DB            │  │   │
│  │  └──────────────────────┘          └───────────────────────────┘  │   │
│  └────────────────────────────────────────────────────────────────────┘   │
└───────────┬────────────────────┬──────────────────────┬──────────────────┘
            │                    │                      │
┌───────────▼──────────┐  ┌──────▼──────────┐  ┌───────▼──────────────────┐
│   DATA LAYER         │  │  DATA SOURCES   │  │  EXTERNAL SERVICES       │
│                      │  │                 │  │                          │
│  ┌────────────────┐  │  │  ┌───────────┐ │  │  ┌────────────────────┐  │
│  │ SQLite DB      │  │  │  │ TfNSW API │ │  │  │ Anthropic API      │  │
│  │                │  │  │  │           │ │  │  │                    │  │
│  │• car_parks     │  │  │  │• Gordon   │ │  │  │• Claude Haiku 4.5  │  │
│  │• occupancy_    │  │  │  │• Lindfield│ │  │  │• Tool calling      │  │
│  │  history       │  │  │  │• 42 others│ │  │  │• max_tokens: 1024  │  │
│  │• parking_signs │  │  │  └───────────┘ │  │  └────────────────────┘  │
│  │                │  │  │                 │  │                          │
│  │90 days history │  │  │  ┌───────────┐ │  │  ┌────────────────────┐  │
│  │(sim backfill)  │  │  │  │ KML File  │ │  │  │ Nominatim          │  │
│  └────────────────┘  │  │  │           │ │  │  │ (OSM Geocoder)     │  │
│                      │  │  │• Willoughby│ │  │  │                    │  │
│  ┌────────────────┐  │  │  │• Signs    │ │  │  │• Reverse geocode   │  │
│  │ Seed Data      │  │  │  │• 1 req/s  │ │  │  │• Street name       │  │
│  │                │  │  │  └───────────┘ │  │  └────────────────────┘  │
│  │• 7 car parks   │  │  │                 │  │                          │
│  │• seed_zones.   │  │  │  ┌───────────┐ │  │                          │
│  │  json          │  │  │  │ Fixtures  │ │  │                          │
│  │  (Victoria Ave)│  │  │  │  (fallback│ │  │                          │
│  └────────────────┘  │  │  │   if no   │ │  │                          │
│                      │  │  │   API key)│ │  │                          │
│                      │  │  └───────────┘ │  │                          │
└──────────────────────┘  └─────────────────┘  └──────────────────────────┘
```

## Data Flow Patterns

### 1. Live Occupancy Request Flow
```
User opens map
   │
   ├─→ Frontend: GET /api/occupancy
   │      │
   │      └─→ occupancy.router
   │             │
   │             └─→ occupancy_service.get_all_occupancy()
   │                    │
   │                    ├─→ DB: SELECT latest occupancy_history
   │                    │
   │                    ├─→ simulator.simulated_available() [for sim parks]
   │                    │
   │                    └─→ Return: OccupancyResponse[] (7 car parks)
   │                           │
   │                           └─→ source: "tfnsw" | "simulated"
   │
   └─→ Frontend: Render 7 markers with color + badge
```

### 2. LLM Chat Request Flow
```
User: "Where to park near Westfield at 6pm Friday?"
   │
   ├─→ POST /api/chat (SSE stream)
   │      │
   │      └─→ chat.router
   │             │
   │             └─→ llm_service.chat_stream() [async generator]
   │                    │
   │                    ├─→ Anthropic API: messages.create()
   │                    │      │
   │                    │      └─→ Tool use: predict_availability
   │                    │
   │                    ├─→ llm_service._dispatch_tool()
   │                    │      │
   │                    │      └─→ prediction_service.predict_availability_tool()
   │                    │             │
   │                    │             └─→ simulator.simulated_available()
   │                    │                    │
   │                    │                    └─→ Return prediction dict
   │                    │
   │                    ├─→ Anthropic API: messages.create() [with tool result]
   │                    │      │
   │                    │      └─→ Return: "Westfield should be 68% full..."
   │                    │
   │                    └─→ Yield SSE chunks:
   │                           data: {"type":"tool_call",...}
   │                           data: {"type":"tool_result",...}
   │                           data: {"type":"text","content":"..."}
   │                           data: {"type":"done"}
   │
   └─→ Frontend: Display streaming response in chat drawer
```

### 3. Background Scheduler Flow
```
APScheduler (runs continuously)
   │
   ├─→ Every 5 minutes: TfNSW Poll Job
   │      │
   │      └─→ occupancy_service.refresh_tfnsw()
   │             │
   │             ├─→ TfNSW API: GET /v1/carpark/full-list
   │             │      │
   │             │      └─→ Returns: 44 facilities (Gordon, Lindfield, etc.)
   │             │
   │             └─→ DB: INSERT OR REPLACE into occupancy_history
   │                    (Gordon: 88 available, Lindfield: 33 available)
   │
   └─→ Every 1 hour: Sim Refresh Job
          │
          └─→ occupancy_service.refresh_sim()
                 │
                 ├─→ For each sim car park (5 total):
                 │      │
                 │      └─→ simulator.simulated_available(dt=now)
                 │
                 └─→ DB: INSERT OR IGNORE into occupancy_history
                        (Westfield: 392/1400 available, etc.)
```

## Key Architectural Principles

### 1. **Separation of Concerns**
- **Frontend**: Pure UI, no business logic
- **Routers**: Thin HTTP adapters, no logic
- **Services**: Pure Python, framework-agnostic, unit-testable
- **Data Layer**: SQLite + external APIs

### 2. **Source Transparency**
- Every response includes `source: "tfnsw" | "simulated"`
- Propagates through: DB → Service → API → Frontend → User
- No layer strips or ignores the source field
- Frontend renders visual badges

### 3. **Graceful Degradation**
- TfNSW API unavailable? → Fall back to fixtures
- KML geocoding fails? → Fall back to `seed_zones.json`
- Anthropic API error? → Service returns error dict (no exceptions)

### 4. **Data Freshness Strategy**
| Data Type | Update Frequency | Method |
|-----------|-----------------|---------|
| Live occupancy (TfNSW) | 5 minutes | APScheduler → DB |
| Simulated occupancy | 1 hour | APScheduler → DB |
| Historical backfill | Once at startup | 90 days × 24 hours |
| Street parking zones | Once at startup | KML parse → DB |
| Predictions | On-demand | Computed per request |

### 5. **Asynchronous Patterns**
- **LLM service**: `AsyncAnthropic` + async generators for SSE
- **Scheduler**: Background thread pool (APScheduler)
- **Frontend polling**: Auto-refresh every 5 min (matches backend poll rate)

## Technology Stack Summary

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | React + Vite + Leaflet | Fast dev, modern, battle-tested mapping |
| Backend | FastAPI | Async support, auto OpenAPI, type safety |
| Database | SQLite (stdlib) | Zero-ops, appropriate scale, WAL mode |
| LLM | GPT mini | Fast, cheap, excellent tool calling |
| ML (Plan 3) | XGBoost + scikit-learn | Best for tabular time-series |
| Scheduler | APScheduler 3.x | Simple, in-process, no Redis needed |
| HTTP Client | httpx | Async support, modern, well-typed |
| Testing | pytest + TestClient | Industry standard |

## Deployment View (Future)

```
┌──────────────────────────────────────────────────────────┐
│  Production Environment (Future)                          │
│                                                            │
│  Frontend: Static hosting (Vercel / Netlify / S3)         │
│  Backend:  Container (Docker) → Cloud Run / Fargate       │
│  Database: SQLite → Persistent volume / Litestream backup │
│  Secrets:  Env vars (TfNSW key, Anthropic key)            │
│  Monitoring: Sentry (errors) + DataDog (metrics)          │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

