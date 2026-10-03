import { mockPlansFor, mockDisrupted, mockCity, mockStations } from "../mocks";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function request(path, options) {
  const res = await fetch(BASE + path, options);
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

const post = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

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