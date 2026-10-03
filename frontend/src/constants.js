export const EVENT_ID = "ev_hackyeah2026";
export const STATION = [50.0677, 19.9479]; // Kraków Główny
export const ARENA = [50.0675, 19.9917]; // Tauron Arena
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