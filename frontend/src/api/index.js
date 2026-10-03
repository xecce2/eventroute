import { mockPlans, mockDisrupted, mockCity } from "../mocks";

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== "false";
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} ${res.status}`);
  return res.json();
}

export async function getPlans(req) {
  if (USE_MOCKS) {
    await sleep(800);
    return mockPlans;
  }
  return post("/api/plan", req);
}

export async function simulateDisruption(planId, delayMin) {
  if (USE_MOCKS) {
    await sleep(500);
    return mockDisrupted;
  }
  return post("/api/simulate/disruption", {
    plan_id: planId,
    train_delay_min: delayMin,
  });
}

export async function getCityOverview() {
  if (USE_MOCKS) {
    await sleep(300);
    return mockCity;
  }
  const res = await fetch(BASE + "/api/city/overview");
  if (!res.ok) throw new Error(`/api/city/overview ${res.status}`);
  return res.json();
}
