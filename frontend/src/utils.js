export const fmt = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  });

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
