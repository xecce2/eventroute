import { useEffect, useState } from "react";
import { FALLBACK_STATIONS, EVENT_ID } from "../constants";
import { getStations } from "../api";

export default function RegistrationForm({ onSubmit, loading }) {
  const [stations, setStations] = useState(FALLBACK_STATIONS);
  const [origin, setOrigin] = useState("Wrocław Główny");
  const [time, setTime] = useState("");
  const [budget, setBudget] = useState("");

  useEffect(() => {
    getStations(EVENT_ID)
      .then((list) => {
        if (!Array.isArray(list) || list.length === 0) return;
        setStations(list);
        setOrigin((cur) => (list.includes(cur) ? cur : list[0]));
      })
      .catch(() => {}); // keep the fallback list
  }, []);

  function submit() {
    onSubmit({
      origin,
      event_id: EVENT_ID,
      arrive_by: time ? `2026-10-04T${time}:00+02:00` : null,
      budget_pln: budget ? Number(budget) : null,
      mode_pref: null,
    });
  }

  return (
    <div className="panel form">
      <div className="event">
        <strong>HackYeah 2026</strong>
        <span>Tauron Arena Kraków · 4 Oct · be at the entrance by 09:30</span>
      </div>
      <label>
        Coming from
        <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
          {stations.map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      <div className="row">
        <label>
          Arrive by (optional)
          <input type="time" value={time} onChange={(e) => setTime(e.target.value)} />
        </label>
        <label>
          Budget, zł (optional)
          <input type="number" min="0" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </label>
      </div>
      <button className="primary" disabled={loading} onClick={submit}>
        {loading ? "Searching for trains…" : "Plan my trip"}
      </button>
    </div>
  );
}