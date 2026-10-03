export const fmt = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  });

const WARSAW = "Europe/Warsaw";
const pad2 = (n) => String(n).padStart(2, "0");

// Offset of Europe/Warsaw from UTC, in minutes, at the given instant (+120 in summer, +60 in winter).
function warsawOffsetAt(ms) {
  const name = new Intl.DateTimeFormat("en-US", { timeZone: WARSAW, timeZoneName: "longOffset" })
    .formatToParts(new Date(ms))
    .find((p) => p.type === "timeZoneName")?.value;
  const m = /GMT([+-])(\d{2}):(\d{2})/.exec(name ?? "");
  return m ? (m[1] === "-" ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3])) : 0;
}

// "2026-10-11" + "09:30" -> "2026-10-11T09:30:00+02:00". The backend rejects a time without an offset,
// and the offset depends on the date (the clocks change on 2026-10-25), so it is worked out here.
export function toArriveBy(date, time) {
  const wallClockAsUtc = Date.parse(`${date}T${time}:00Z`);
  const first = warsawOffsetAt(wallClockAsUtc);
  const offset = warsawOffsetAt(wallClockAsUtc - first * 60000); // second pass, right at a clock change
  const abs = Math.abs(offset);
  return `${date}T${time}:00${offset < 0 ? "-" : "+"}${pad2(Math.floor(abs / 60))}:${pad2(abs % 60)}`;
}

// The wall clock in Warsaw at an instant: { date: "2026-10-04", time: "09:30" }.
export function warsawDateTime(ms) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: WARSAW, year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(new Date(ms)).map((p) => [p.type, p.value]),
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}

// Default "be at the entrance by": the event start minus the check-in buffer.
export const eventTarget = (event) =>
  warsawDateTime(Date.parse(event.start) - (event.checkin_buffer_min ?? 0) * 60000);

// The Warsaw calendar day of an instant: "2026-10-11".
export const dayOf = (iso) => warsawDateTime(Date.parse(iso)).date;

const shortDay = (date) =>
  new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", { weekday: "short", day: "numeric", timeZone: "UTC" });

// "21:30", or "Sat 10 21:30" when it is not the day of `refIso` (the day to be at the entrance).
// With a chosen date the evening before is a different day, and the hours alone would hide that.
export const stamp = (iso, refIso) =>
  !refIso || dayOf(iso) === dayOf(refIso) ? fmt(iso) : `${shortDay(dayOf(iso))} ${fmt(iso)}`;

export const longDate = (date) =>
  new Date(`${date}T12:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short", timeZone: "UTC",
  });

// "3h 05min" for a trip between two instants.
export const fmtDuration = (depIso, arrIso) => {
  const minutes = Math.round((Date.parse(arrIso) - Date.parse(depIso)) / 60000);
  const h = Math.floor(minutes / 60);
  return h ? `${h}h ${pad2(minutes % 60)}min` : `${minutes}min`;
};

// Always two decimals, so "64.00" and "39.98" line up; null stays null (the price is on the site).
export const fmtPrice = (zloty) => (zloty == null ? null : zloty.toFixed(2));

export const probColor = (p) =>
  p >= 0.9 ? "var(--good)" : p >= 0.7 ? "var(--warn)" : "var(--bad)";

export const isLive = (source) => source === "koleo" || source === "playwright";

// Only the frontend mocks use this source; the backend never sends it.
export const isMock = (source) => source === "mock";

export const sourceBadge = (source) =>
  isMock(source)
    ? { className: "mock", text: "Mock data (not real)" }
    : isLive(source)
      ? { className: "live", text: "Live" }
      : { className: "grey", text: "Recorded data" };
