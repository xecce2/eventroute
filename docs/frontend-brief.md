# EventRoute: data and screens for the frontend

Paste this whole file into a Claude chat and ask for the design and components. The contracts in `CLAUDE.md` (section 4) stay the source of truth: if they disagree with this file, `CLAUDE.md` wins.

## What the product is

A HackYeah 2026 participant (Tauron Arena, Kraków, 4 October, starts 10:00, be at the entrance by 09:30) picks the station they travel from and gets up to three plans: a train or bus to Kraków, then a tram and a walk to the entrance. Every plan shows the chance of arriving on time. A "train delayed 25 min" button recalculates the plan. A separate screen shows the organiser and the city the wave of arrivals.

All UI text and all API texts are **English**. Times are ISO 8601 with an offset (`2026-10-04T08:48:00+02:00`): display them in Europe/Warsaw. Money is in zloty (`price_pln`).

## Connecting

- Backend: `http://localhost:8000`, schemas and a try-it page at `http://localhost:8000/docs`.
- If an endpoint is not ready yet, work on mocks in the shapes below.

## Screens

1. **Registration form.** Origin station dropdown filled from `GET /api/events/{id}/stations`, optional "arrive by" and budget. Default to `Wrocław Główny` for the demo.
2. **Plans.** 1 to 3 cards. One card can carry several labels at once (`safest`, `fastest`, `cheapest`). A card shows: labels, chance of arriving on time (the main element, e.g. a gauge), spare time in minutes, price or "price on site" when `null`, a train or bus icon, an "overnight stay" badge, a "Buy on Koleo" button (`buy_url`), the short `explanation`, and a data source badge (see below).
3. **All options list.** Under the cards, a list of every suitable option (`options`), cheapest first. Options that are not cards have `labels: []`. Clicking one should be able to run the delay simulation for it.
4. **Timeline and map.** A vertical timeline of the trip: train departure, arrival, walk, tram, walk, entrance, plus "be at the entrance by 09:30". A Leaflet/OSM map of the part after the train: markers for the station and the arena, a line from `local_legs[].path`, a different style per leg (dashed for walking, solid with the line number for the tram).
5. **Rescheduling.** A "Train delayed 25 min" button. Shows before and after: chance, spare time, arrival time, plus the `message` text. If there is no alternative, say so explicitly.
6. **City screen.** A bar chart of arrivals per 15-minute slot, node cards with load level (`low | medium | high`), where people come from (`origins`), recommendations with severity.

## Data

### Event
`GET /api/events/ev_hackyeah2026`:
```json
{"id": "ev_hackyeah2026", "name": "HackYeah 2026", "venue": "Tauron Arena Kraków",
 "venue_station": "Kraków Główny", "city": "Kraków", "start": "2026-10-04T10:00:00+02:00",
 "checkin_buffer_min": 30, "lat": 50.0675, "lon": 19.9917}
```

### Stations for the dropdown
`GET /api/events/ev_hackyeah2026/stations`:
```json
["Katowice", "Poznań Główny", "Warszawa Centralna", "Wrocław Główny"]
```
Send the chosen value as `origin` unchanged.

### Plans
`POST /api/plan`, body `{"origin": "Wrocław Główny", "event_id": "ev_hackyeah2026", "arrive_by": null, "budget_pln": null, "mode_pref": null}`.
`budget_pln` must be above 0 (with a budget, options without a price are left out). `mode_pref` is `"train"`, `"bus"` or `null` (both). `arrive_by` may be any date and time with a time zone (the event is the place, its start is only the default); the search covers the 12 hours before it. `arrive_by` without a time zone, a budget of 0 or less and any other `mode_pref` give HTTP 422.
Response: `{request_id, plans: Plan[], options: Plan[], status: "ok" | "no_options"}`.

- `plans`: the cards, 1 to 3 plans with labels.
- `options`: **all** suitable options, cheapest first (ties by departure time, options without a price last). It includes the cards (same `id`) and options with `overnight_stay: true`. For Wrocław it currently returns 9 options, and some of them are overnight (arriving before 06:00), so give `overnight_stay` a clear visual treatment or the list will look misleading.
- On `no_options` show a clear "no suitable options" state.

Real example of one plan (Wrocław), with `path` points shortened:
```json
{
  "id": "pl_066e7559",
  "labels": ["safest", "fastest"],
  "train": {
    "id": "tr_wro_1004_0510", "source": "fixture", "mode": "train", "category": "IC", "train": "IC",
    "from": "Wrocław Główny", "to": "Kraków Główny",
    "dep": "2026-10-04T05:10:00+02:00", "arr": "2026-10-04T08:15:00+02:00",
    "price_pln": 64.0, "changes": 0, "known_delay_min": 0,
    "delay_model": {"p_on_time": 0.7, "mean_delay_min": 6, "p95_delay_min": 25},
    "url": "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_05:10/all/all"
  },
  "local_legs": [
    {"mode": "walk", "from": "Kraków Główny", "to": "Dworzec Główny Tunel",
     "dep": "2026-10-04T08:20:00+02:00", "arr": "2026-10-04T08:23:00+02:00",
     "duration_min": 3, "std_min": 1, "line": null, "path": [[50.0677, 19.9479], "..."]},
    {"mode": "tram", "from": "Dworzec Główny Tunel", "to": "TAURON Arena Kraków Wieczysta",
     "dep": "2026-10-04T08:23:00+02:00", "arr": "2026-10-04T08:36:00+02:00",
     "duration_min": 13, "std_min": 3, "line": "15", "path": [[50.068199, 19.947649], "..."]},
    {"mode": "walk", "from": "TAURON Arena Kraków Wieczysta", "to": "Tauron Arena Kraków",
     "dep": "2026-10-04T08:36:00+02:00", "arr": "2026-10-04T08:48:00+02:00",
     "duration_min": 12, "std_min": 2, "line": null, "path": [[50.071785, 19.983839], "..."]}
  ],
  "venue_target": "2026-10-04T09:30:00+02:00",
  "arrival_at_venue": "2026-10-04T08:48:00+02:00",
  "buffer_min": 42,
  "p_on_time": 0.983,
  "price_pln": 64.0,
  "overnight_stay": false,
  "explanation": "Most reliable, fastest. 42 min to spare, 98% chance of arriving on time.",
  "buy_url": "https://koleo.pl/rozklad-pkp/wroclaw-glowny/krakow-glowny/04-10-2026_05:10/all/all"
}
```

How to read the fields:
- `train.mode` is `train` or `bus` (FlixBus); a bus gets its own icon. `train.category` is one of `IC`, `TLK`, `EIP`, `EIC`, `LEO`, `FLIX`, `PR`, `KŚ`, `KM`; routes with a change are joined with a plus, e.g. `IC+EIP`. `train.changes` is the number of changes.
- `price_pln` can be `null`: show "price on site". Such a plan is never `cheapest`.
- `buffer_min` can be negative: the traveller is late, show it in red as "X min late".
- `p_on_time` is from 0 to 1. Pick colour thresholds in the design; a guide: 0.9 and up is safe, 0.7 and up is fine, below that is risky.
- `overnight_stay: true` means the train arrives the day before or overnight, so the traveller needs a place to stay. Show it as a warning. Such a plan is never `fastest` or `cheapest`.
- If a `local_legs[].path` is `null`, draw a straight line between the station (50.0677, 19.9479) and the arena (`Event.lat/lon`).
- `path` points are `[lat, lon]`, the order Leaflet uses.
- `known_delay_min` above 0 means the train is already late; the planned `arr` does not change.

### Search progress
`GET /api/plan/{request_id}/stream` (SSE). Events `event: status` with `data: {"step": "search|found|local|reliability|done", "message": "Searching for trains…"}` and `event: done` at the end. Show it as a short list of steps under the form while the search runs.

### Delay
`POST /api/simulate/disruption`, body `{"plan_id": "pl_066e7559", "train_delay_min": 25}`. `plan_id` can be any `id` from `plans` or `options`. Response:
```json
{"affected_plan": { "...Plan, train.known_delay_min = 25, p_on_time 0.776, buffer_min 17, arrival_at_venue 09:13" },
 "plans": [ "...recalculated cards" ],
 "options": [ "...recalculated list, same rules as in POST /api/plan" ],
 "notified": false,
 "message": "IC 05:10 is delayed by 25 min. You will arrive around 09:13, 78% chance of arriving on time."}
```
`affected_plan` is for "before and after" (compare it with the original plan). Alternatives only include departures not earlier than the delayed train. `notified: false` means the Telegram message was not sent; show `message` in the UI as the notification. The delay is recalculated from the options of the original search (no new search), so the answer is instant and every `train.id` is one you already have.

### City screen
`GET /api/city/overview` (the `event_id` query parameter is optional while there is one event). Real response, shortened:
```json
{"event_id": "ev_hackyeah2026", "participants_total": 420,
 "arrivals_by_slot": [{"slot": "2026-10-04T06:30:00+02:00", "count": 18},
                      {"slot": "2026-10-04T06:45:00+02:00", "count": 0}],
 "nodes": [
   {"name": "Kraków Główny", "lat": 50.0677, "lon": 19.9479, "peak_count": 151,
    "peak_slot": "2026-10-04T08:15:00+02:00", "load": "high"},
   {"name": "Tauron Arena Kraków", "lat": 50.0675, "lon": 19.9917, "peak_count": 151,
    "peak_slot": "2026-10-04T08:45:00+02:00", "load": "high"}],
 "origins": [{"station": "Warszawa Centralna", "count": 167}, {"station": "Katowice", "count": 88}],
 "recommendations": [
   {"type": "add_trams", "severity": "high",
    "text": "151 participants arrive at Kraków Główny at 08:15–08:30. Add trams towards Tauron Arena Kraków from 08:15 to 08:45."}]}
```
- Slots are 15 minutes and consecutive, empty ones have `count: 0`. `arrivals_by_slot` counts arrivals **at the entrance**.
- `load` is `low | medium | high`; `peak_slot` can be `null` when nobody arrives.
- `recommendations` exist only for `medium` and `high` nodes, `high` first. `type` is `stagger_checkin` or `add_trams`.
- `participants_total` and `origins` include everyone, but people who stay overnight or have no suitable plan are not in the wave.
- The participants are synthetic, not real people: say so on the screen in small text.

## Data source: "live" or "recorded"

We do not want the demo to look like a live agent when it is really replaying recorded data, so the data source must always be visible.

- Already there: `plan.train.source`. `koleo` and `playwright` mean a live search; `fixture` means recorded Koleo data from 3 October. Right now it is `fixture` everywhere.
- **Badge on a plan card:** show `fixture` as "Recorded data" (calm grey) and `koleo` / `playwright` as "Live" (accent colour). The badge must not be tiny or hidden: it is part of an honest presentation.
- **Planned, not implemented yet (build against mocks):**
  - `POST /api/plan` gains `data_source: "live" | "recorded" | "mixed"` and `fallback_reason: string | null` (for example "live search failed: rate limit"; `null` when there was no fallback). When `fallback_reason` is set, show a one-line banner above the plans: "Live search failed, showing recorded data".
  - SSE gains a `step: "fallback"` with the reason in `message`.
  - `GET /api/providers/status` returns `{provider, live_available, requests_total, live_ok, live_partial, fallback, last_fallback_reason, last_rejection_reason}`, for a small corner indicator or a service screen.

## What we need from the design

A clean, modern interface for a stage demo: readable from a distance, not crowded, with the chance of arriving on time and the "when to leave" time as the most visible elements. Light and dark themes are optional. A phone layout is needed (participants use phones); the city screen is for a laptop or projector first.
