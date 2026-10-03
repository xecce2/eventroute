import { useState } from "react";
import { getPlans, simulateDisruption } from "./api";

export default function App() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notified, setNotified] = useState(false);

  async function onFind() {
    setLoading(true);
    setError(null);
    setNotified(false);
    try {
      const data = await getPlans({
        origin: "Wrocław Główny",
        event_id: "ev_hackyeah2026",
        arrive_by: null,
      });
      setPlans(data.plans);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function onDelay() {
    if (plans.length === 0) return;
    setLoading(true);
    setError(null);
    try {
      const data = await simulateDisruption(plans[0].id, 25);
      setPlans(data.plans);
      setNotified(data.notified);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ padding: 24, textAlign: "left" }}>
      <h1>EventRoute</h1>

      <button onClick={onFind} disabled={loading}>
        Find plans
      </button>{" "}
      <button onClick={onDelay} disabled={loading || plans.length === 0}>
        Train delayed 25 min
      </button>

      {loading && <p>Searching for trains...</p>}
      {error && <p style={{ color: "crimson" }}>Error: {error}</p>}
      {notified && <p>Telegram notification sent</p>}

      {plans.map((p) => (
        <div
          key={p.id}
          style={{ border: "1px solid #888", borderRadius: 8, padding: 12, marginTop: 12 }}
        >
          <strong>{p.labels.join(", ")}</strong>
          <div>
            {p.train.train}: {p.train.from} to {p.train.to}
          </div>
          <div>
            Chance to make it: {Math.round(p.p_on_time * 100)}%, buffer {p.buffer_min} min
          </div>
          <div>Known delay: {p.train.known_delay_min} min</div>
          <div>{p.explanation}</div>
          <a href={p.buy_url} target="_blank" rel="noreferrer">
            Buy ticket
          </a>
        </div>
      ))}
    </div>
  );
}