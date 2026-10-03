// ---------- helpers ----------
// All times are minutes counted from 2026-10-03 00:00 (so 4 Oct 08:15 = 1440 + 495).
const D4 = 1440;
const TARGET = D4 + 9 * 60 + 30; // be at the entrance by 09:30 on 4 Oct

const pad = (n) => String(n).padStart(2, "0");
const iso = (abs) => {
  const day = 3 + Math.floor(abs / 1440);
  const rem = abs % 1440;
  return `2026-10-${pad(day)}T${pad(Math.floor(rem / 60))}:${pad(rem % 60)}:00+02:00`;
};
const hhmm = (abs) => `${pad(Math.floor((abs % 1440) / 60))}:${pad(abs % 60)}`;
const slug = (s) =>
  s.replace(/ł/g, "l").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, "-");

const probFor = (buffer, mode) => Math.max(0.05, Math.min(0.99, 0.6 + buffer / 120 - (mode === "bus" ? 0.07 : 0)));

// ---------- fake timetable per origin ----------
// day: 0 = 3 Oct (evening before), 1 = 4 Oct. dep/arr are minutes within that day.
const ROUTES = {
  "Wrocław Główny": [
    { mode: "train", category: "IC", train: "IC", day: 1, dep: 310, arr: 495, price: 64 },
    { mode: "bus", category: "FLIX", train: "FlixBus", day: 1, dep: 250, arr: 490, price: 25 },
    { mode: "train", category: "IC", train: "IC", day: 0, dep: 1150, arr: 1335, price: 39 },
  ],
  "Warszawa Centralna": [
    { mode: "train", category: "EIP", train: "EIP", day: 1, dep: 330, arr: 480, price: 129 },
    { mode: "bus", category: "FLIX", train: "FlixBus", day: 1, dep: 210, arr: 500, price: 35 },
    { mode: "train", category: "IC", train: "IC", day: 0, dep: 1080, arr: 1230, price: 79 },
  ],
  "Poznań Główny": [
    { mode: "train", category: "IC", train: "IC", day: 1, dep: 220, arr: 505, price: 89 },
    { mode: "bus", category: "FLIX", train: "FlixBus", day: 1, dep: 120, arr: 480, price: 30 },
    { mode: "train", category: "IC", train: "IC", day: 0, dep: 1020, arr: 1330, price: 55 },
  ],
  Katowice: [
    { mode: "train", category: "IC", train: "IC", day: 1, dep: 390, arr: 490, price: 39 },
    { mode: "bus", category: "FLIX", train: "FlixBus", day: 1, dep: 330, arr: 480, price: 15 },
    { mode: "train", category: "IC", train: "IC", day: 0, dep: 1140, arr: 1240, price: 29 },
  ],
};

// Straight-line approximations; the real backend sends full paths.
const PATHS = {
  walk1: [[50.0677, 19.9479], [50.068199, 19.947649]],
  tram: [[50.068199, 19.947649], [50.0705, 19.965], [50.071785, 19.983839]],
  walk2: [[50.071785, 19.983839], [50.0675, 19.9917]],
};

function legsFrom(arrAbs) {
  const t0 = arrAbs + 5;
  return [
    { mode: "walk", from: "Kraków Główny", to: "Dworzec Główny Tunel",
      dep: iso(t0), arr: iso(t0 + 3), duration_min: 3, std_min: 1, line: null, path: PATHS.walk1 },
    { mode: "tram", from: "Dworzec Główny Tunel", to: "TAURON Arena Kraków Wieczysta",
      dep: iso(t0 + 3), arr: iso(t0 + 16), duration_min: 13, std_min: 3, line: "15", path: PATHS.tram },
    { mode: "walk", from: "TAURON Arena Kraków Wieczysta", to: "Tauron Arena Kraków",
      dep: iso(t0 + 16), arr: iso(t0 + 28), duration_min: 12, std_min: 2, line: null, path: PATHS.walk2 },
  ];
}

function buildPlan(origin, r, i) {
  const base = r.day * D4;
  const dep = base + r.dep;
  const arr = base + r.arr;
  const atVenue = arr + 33;
  const buffer = TARGET - atVenue;
  const url = `https://koleo.pl/rozklad-pkp/${slug(origin)}/krakow-glowny/${r.day ? "04" : "03"}-10-2026_${hhmm(dep)}/all/all`;
  return {
    id: `pl_${slug(origin)}_${i}`,
    labels: [],
    train: {
      id: `tr_${slug(origin)}_${i}`, source: "fixture", mode: r.mode, category: r.category, train: r.train,
      from: origin, to: "Kraków Główny", dep: iso(dep), arr: iso(arr),
      price_pln: r.price, changes: 0, known_delay_min: 0,
      delay_model: { p_on_time: 0.7, mean_delay_min: 6, p95_delay_min: 25 }, url,
    },
    local_legs: legsFrom(arr),
    venue_target: iso(TARGET),
    arrival_at_venue: iso(atVenue),
    buffer_min: buffer,
    p_on_time: probFor(buffer, r.mode),
    price_pln: r.price,
    overnight_stay: r.day === 0,
    explanation: "",
    buy_url: url,
    _dur: arr - dep, // internal, used for labels
  };
}

let lastOptions = [];

export function mockPlansFor(req) {
  const origin = ROUTES[req.origin] ? req.origin : "Wrocław Główny";
  let options = ROUTES[origin].map((r, i) => buildPlan(origin, r, i));
  if (req.budget_pln != null) options = options.filter((o) => o.price_pln <= req.budget_pln);

  const dayOf = options.filter((o) => !o.overnight_stay && o.buffer_min >= 0);
  if (dayOf.length) {
    const best = (key, dir) => dayOf.reduce((a, b) => (dir * (b[key] - a[key]) < 0 ? b : a));
    best("p_on_time", -1).labels.push("safest");
    best("_dur", 1).labels.push("fastest");
    best("price_pln", 1).labels.push("cheapest");
  }
  options.forEach((o) => {
    const pct = Math.round(o.p_on_time * 100);
    o.explanation = o.overnight_stay
      ? "Arrives the evening before. You need a place to stay."
      : `${o.labels.length ? o.labels.join(", ") + ". " : ""}${o.buffer_min} min to spare, ${pct}% chance of arriving on time.`;
  });

  options.sort((a, b) => a.price_pln - b.price_pln || a.train.dep.localeCompare(b.train.dep));
  lastOptions = options;
  const plans = options.filter((o) => o.labels.length > 0);
  return {
    request_id: "req_mock",
    status: options.length ? "ok" : "no_options",
    data_source: "recorded",
    fallback_reason: null,
    plans,
    options,
  };
}

export function mockDisrupted(planId) {
  const base = lastOptions.find((p) => p.id === planId) ?? lastOptions[0];
  const delay = 25;
  const buffer = base.buffer_min - delay;
  const arrAbs = TARGET - buffer;
  const affected = {
    ...base,
    train: { ...base.train, known_delay_min: delay },
    buffer_min: buffer,
    p_on_time: probFor(buffer, base.train.mode),
    arrival_at_venue: iso(arrAbs),
  };
  const swap = (list) => list.map((p) => (p.id === affected.id ? affected : p));
  lastOptions = swap(lastOptions);
  return {
    affected_plan: affected,
    plans: swap(lastOptions.filter((o) => o.labels.length > 0)),
    options: lastOptions,
    notified: false,
    message: `${base.train.train} is delayed by ${delay} min. You will arrive around ${hhmm(arrAbs)}, ${Math.round(affected.p_on_time * 100)}% chance of arriving on time.`,
  };
}

export const mockStations = Object.keys(ROUTES).sort();

export const mockCity = {
  event_id: "ev_hackyeah2026", participants_total: 420,
  arrivals_by_slot: [
    { slot: "2026-10-04T08:00:00+02:00", count: 25 },
    { slot: "2026-10-04T08:15:00+02:00", count: 60 },
    { slot: "2026-10-04T08:30:00+02:00", count: 112 },
    { slot: "2026-10-04T08:45:00+02:00", count: 140 },
    { slot: "2026-10-04T09:00:00+02:00", count: 70 },
    { slot: "2026-10-04T09:15:00+02:00", count: 13 },
  ],
  nodes: [
    { name: "Kraków Główny", lat: 50.0677, lon: 19.9479, peak_count: 140,
      peak_slot: "2026-10-04T08:45:00+02:00", load: "high" },
    { name: "Tauron Arena Kraków", lat: 50.0675, lon: 19.9917, peak_count: 95,
      peak_slot: "2026-10-04T08:45:00+02:00", load: "medium" },
  ],
  origins: [
    { station: "Warszawa Centralna", count: 150 },
    { station: "Wrocław Główny", count: 120 },
    { station: "Katowice", count: 90 },
    { station: "Poznań Główny", count: 60 },
  ],
  recommendations: [
    { type: "add_trams", severity: "high",
      text: "140 participants arrive at Kraków Główny at 08:45. Add trams towards Tauron Arena Kraków from 08:45 to 09:15." },
  ],
};