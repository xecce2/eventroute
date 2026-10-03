import { mockPlansFor, mockDisrupted, mockCity, mockStations, mockEvent } from "../mocks";

// Mocks are invented data: they are on only when asked for explicitly (VITE_USE_MOCKS=true).
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "true";
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// The server explains a refusal (FastAPI: `detail` is a text or a list of {msg}); show that, not just a code.
async function failure(path, res) {
  let reason = "";
  try {
    const { detail } = await res.json();
    reason = Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : String(detail ?? "");
  } catch {
    // no JSON body: the status code is all there is
  }
  return new Error(reason ? `${reason} (${res.status})` : `${path} ${res.status}`);
}

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) throw await failure(path, res);
  return res.json();
}

const post = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export async function getEvent(eventId) {
  if (USE_MOCKS) {
    await sleep(100);
    return mockEvent;
  }
  return request(`/api/events/${eventId}`);
}

export async function getStations(eventId) {
  if (USE_MOCKS) {
    await sleep(100);
    return mockStations;
  }
  return request(`/api/events/${eventId}/stations`);
}

export async function getPlans(req) {
  if (USE_MOCKS) {
    await sleep(900);
    return mockPlansFor(req);
  }
  return post("/api/plan", req);
}

export async function simulateDisruption(planId, delayMin) {
  if (USE_MOCKS) {
    await sleep(500);
    return mockDisrupted(planId);
  }
  return post("/api/simulate/disruption", { plan_id: planId, train_delay_min: delayMin });
}

export async function getCityOverview(eventId) {
  if (USE_MOCKS) {
    await sleep(300);
    return mockCity;
  }
  return request(`/api/city/overview?event_id=${eventId}`);
}