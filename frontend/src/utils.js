export const fmt = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Warsaw",
  });

export const probColor = (p) =>
  p >= 0.9 ? "var(--good)" : p >= 0.7 ? "var(--warn)" : "var(--bad)";

export const isLive = (source) => source === "koleo" || source === "playwright";
