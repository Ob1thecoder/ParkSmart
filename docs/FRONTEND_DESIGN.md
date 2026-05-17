# ParkSmart Frontend Design System

This document describes the frontend architecture, design tokens, and component structure.

## Tech Stack

| Technology | Purpose |
|------------|---------|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite | Build tool |
| Tailwind CSS | Styling |
| Leaflet | Map rendering |
| React Leaflet | React bindings for Leaflet |

---

## Design Tokens

### Color Palette

```css
/* Primary colors - Nature-inspired theme */
park-ink:    #0c1a14   /* Deep forest green - text, headers */
park-mist:   #e8f2ec   /* Light sage - backgrounds */
park-fern:   #1f6b4a   /* Vibrant green - primary accent, CTAs */
park-amber:  #c9780a   /* Warm amber - warnings, medium availability */
park-brick:  #b4232c   /* Brick red - errors, low availability */
park-slate:  #5c6f66   /* Muted green-gray - secondary text */

/* Background colors */
warm:        #faf9f6   /* Warm off-white */
greeting:    #f0f8f3   /* Light green tint for welcome messages */
```

### Availability Color Coding

| Status | Color | Usage |
|--------|-------|-------|
| High availability (>50%) | `park-fern` (#1f6b4a) | Green markers, positive indicators |
| Medium availability (20-50%) | `park-amber` (#c9780a) | Amber markers, caution |
| Low availability (<20%) | `park-brick` (#b4232c) | Red markers, warning |
| Loading/Pending | Gray with pulse animation | Skeleton states |

### Typography

```css
/* Display font - Headers, branding */
font-display: 'Syne', system-ui, sans-serif;

/* Body font - Content, UI elements */
font-sans: 'DM Sans', system-ui, sans-serif;
```

| Element | Font | Size | Weight |
|---------|------|------|--------|
| App title | Syne | 16px (base) | 600 (semibold) |
| Panel header | Syne | 14px (sm) | 600 (semibold) |
| Body text | DM Sans | 14px | 400 (normal) |
| Small text | DM Sans | 12px (xs) | 400-500 |
| Micro text | DM Sans | 10px | 500 (medium) |

### Shadows

```css
shadow-sheet:  0 -8px 40px rgba(12, 26, 20, 0.12)   /* Mobile bottom sheet */
shadow-drawer: -4px 0 32px rgba(12, 26, 20, 0.08)   /* Desktop side panel */
shadow-subtle: 0 1px 4px rgba(0, 0, 0, 0.04)        /* Cards, headers */
```

---

## Layout Structure

### Desktop Layout (≥768px)

```
┌─────────────────────────────────────────────────────────────────┐
│ Header: Logo + Location Badge                                    │
├────────────────────────────────────────────┬────────────────────┤
│                                            │                    │
│                                            │   Assistant Panel  │
│              Interactive Map               │   (380px fixed)    │
│                                            │                    │
│   ┌──────────────┐                        │   ┌──────────────┐ │
│   │ Search Field │                        │   │ Tab Bar      │ │
│   │ Zone Rules   │                        │   │ Chat | Parks │ │
│   └──────────────┘                        │   ├──────────────┤ │
│                                            │   │ Content      │ │
│   ┌──────────────┐                        │   │              │ │
│   │ Time Scrubber│                        │   └──────────────┘ │
│   └──────────────┘                        │   ┌──────────────┐ │
│                                            │   │ Message Input│ │
│                                            │   └──────────────┘ │
└────────────────────────────────────────────┴────────────────────┘
```

### Mobile Layout (<768px)

```
┌─────────────────────────┐
│ Header                  │
├─────────────────────────┤
│                         │
│    Interactive Map      │
│    (min 50vh)           │
│                         │
│  ┌───────────────────┐  │
│  │ Search + Zones    │  │
│  └───────────────────┘  │
│                         │
│  ┌───────────────────┐  │
│  │ Time Scrubber     │  │
│  └───────────────────┘  │
│                         │
│  ╭─────────────────────╮│
│  │ "Ask Valet..." FAB  ││
│  ╰─────────────────────╯│
└─────────────────────────┘

     ▼ Tap FAB ▼

┌─────────────────────────┐
│ Header                  │
├─────────────────────────┤
│    Map (compressed)     │
├─────────────────────────┤
│ ╭─────────────────────╮ │
│ │   Bottom Sheet      │ │
│ │   (max 85vh)        │ │
│ │   rounded-t-3xl     │ │
│ │                     │ │
│ │   Chat / Car Parks  │ │
│ │                     │ │
│ ╰─────────────────────╯ │
└─────────────────────────┘
```

---

## Component Hierarchy

```
App
├── ChatProvider (Context)
└── Shell
    ├── Header
    ├── MapView
    │   ├── TileLayer (OpenStreetMap)
    │   └── CarParkMarker[] (custom Leaflet markers)
    ├── SearchField (floating overlay)
    ├── ZoneRulesCard (collapsible)
    ├── TimeScrubber (time selection)
    └── AssistantPanel
        ├── VAvatar (Valet icon)
        ├── TabBar (Chat | Car Parks)
        ├── MessageList
        │   ├── MessageBubble (user/assistant)
        │   └── ToolResultCard (function results)
        ├── CarParksTab
        └── MessageInput
```

---

## Key Components

### 1. Header
- Dark background (`park-ink`)
- App name "ParkChatswood" in display font
- Location badge "Chatswood" in `park-fern`

### 2. MapView
- Leaflet map with OpenStreetMap tiles
- Custom markers showing availability
- Click to select car park
- Supports zoom and pan

### 3. AssistantPanel ("Valet")
- AI chat assistant
- Car parks list view
- Mobile: bottom sheet with drag handle
- Desktop: fixed right sidebar (380px)

### 4. TimeScrubber
- Horizontal time selector
- "Now" button for live data
- Future times for predictions
- Visual feedback for loading states

### 5. CarParkMarker
- Circle marker with availability percentage
- Color-coded (green/amber/red)
- Pulse animation for live data
- Different state for predictions

### 6. ZoneRulesCard
- Expandable street parking rules
- Shows time restrictions
- Color-coded rule categories

---

## Animations

| Animation | Duration | Purpose |
|-----------|----------|---------|
| `dot-jump` | 1.2s | Typing indicator dots |
| `live-pulse` | 1.9s | Status indicator pulse |
| `slide-in` | 0.16s | Card/message appear |
| `ps-shimmer` | 1.5s | Skeleton loading |
| `ps-bar-slide` | 1.4s | Progress bar indeterminate |
| `ps-live-pulse` | 1.9s | Live data indicator ring |

---

## Responsive Breakpoints

| Breakpoint | Width | Behavior |
|------------|-------|----------|
| Mobile | <768px | Bottom sheet, FAB, stacked layout |
| Desktop | ≥768px | Side panel, full map, horizontal layout |

---

## State Management

### ChatContext
- `messages`: Chat history array
- `busy`: Loading state
- `error`: Error message
- `sendMessage()`: Send user message
- `retryChat()`: Retry failed message
- `clearError()`: Dismiss error

### URL/API Configuration
```typescript
const API_BASE = import.meta.env.VITE_API_URL || "";
```

For local development, Vite proxy handles `/api` routes.
For production, `VITE_API_URL` points to Fly.io backend.

---

## File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── Assistant/
│   │   │   ├── AssistantPanel.tsx    # Main chat panel
│   │   │   ├── CarParksTab.tsx       # Car parks list
│   │   │   ├── MessageBubble.tsx     # Chat message
│   │   │   ├── MessageInput.tsx      # Text input
│   │   │   ├── MessageList.tsx       # Messages container
│   │   │   └── ToolResultCard.tsx    # AI tool results
│   │   ├── Map/
│   │   │   ├── MapView.tsx           # Leaflet map
│   │   │   ├── CarParkMarker.tsx     # Custom marker
│   │   │   └── CarParkDetail.tsx     # Selected park info
│   │   ├── Scrubber/
│   │   │   └── TimeScrubber.tsx      # Time selector
│   │   └── Zones/
│   │       ├── SearchField.tsx       # Street search
│   │       └── ZoneRulesCard.tsx     # Parking rules
│   ├── context/
│   │   └── ChatContext.tsx           # Chat state
│   ├── hooks/
│   │   ├── useOccupancy.ts           # Live occupancy data
│   │   ├── usePredictions.ts         # Future predictions
│   │   ├── useZones.ts               # Street parking rules
│   │   └── useMediaQuery.ts          # Responsive detection
│   ├── lib/
│   │   ├── buildMarkers.ts           # Marker data builder
│   │   └── formatStreetRules.ts      # Rules formatter
│   ├── api.ts                        # API client
│   ├── types.ts                      # TypeScript types
│   ├── App.tsx                       # Root component
│   ├── main.tsx                      # Entry point
│   └── index.css                     # Global styles
├── tailwind.config.js                # Tailwind config
├── vite.config.ts                    # Vite config
└── package.json
```

---

## Accessibility

- Semantic HTML (`header`, `aside`, `button`)
- Focus states on interactive elements
- Color contrast meets WCAG AA
- Touch targets ≥44px on mobile
- Loading states announced to screen readers

---

## Performance Optimizations

1. **Code splitting**: Vite handles automatic chunk splitting
2. **Memoization**: `useMemo` for expensive calculations
3. **Lazy loading**: Map tiles load on demand
4. **Debounced search**: Prevents excessive API calls
5. **Optimistic UI**: Immediate feedback on user actions
