export const EVENT_ID = "ev_hackyeah2026";
export const STATION = [50.0677, 19.9479]; // Kraków Główny
export const ARENA = [50.0675, 19.9917]; // Tauron Arena
// A date ("2026-10-11") the form starts with instead of the event's own day. Set VITE_DEFAULT_DATE in
// frontend/.env.local for the pitch, when the trains to the event day have already left.
export const DEFAULT_DATE = import.meta.env.VITE_DEFAULT_DATE || null;

// Shown until GET /api/events/{id} answers (and if it never does).
export const FALLBACK_EVENT = {
  name: "HackYeah 2026",
  venue: "Tauron Arena Kraków",
  start: "2026-10-04T10:00:00+02:00",
  checkin_buffer_min: 30,
};
export const FALLBACK_STATIONS = [
  "Katowice",
  "Poznań Główny",
  "Warszawa Centralna",
  "Wrocław Główny",
];