import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { getCityOverview } from "../api";
import { EVENT_ID } from "../constants";
import { fmt } from "../utils";

export default function CityDashboard() {
  const [city, setCity] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCityOverview(EVENT_ID).then(setCity).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="bad">Error: {error}</p>;
  if (!city) return <p>Loading city overview…</p>;

  const data = city.arrivals_by_slot.map((s) => ({ time: fmt(s.slot), count: s.count }));

  return (
    <div className="city">
      <div className="panel">
        <h3>Arrivals at the entrance ({city.participants_total} participants)</h3>
        <div style={{ height: 260 }}>
          <ResponsiveContainer>
            <BarChart data={data}>
              <XAxis dataKey="time" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="count" fill="#1a56db" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <small className="muted">
          Synthetic participants, not real people. Those staying overnight are not in the wave.
        </small>
      </div>

      <div className="panel">
        <h3>Hubs</h3>
        {city.nodes.map((n) => (
          <div key={n.name} className="row between">
            <span>
              {n.name}{" "}
              <small className="muted">
                {n.peak_slot ? `peak ${fmt(n.peak_slot)}, ${n.peak_count}` : "no arrivals"}
              </small>
            </span>
            <span className={`badge load-${n.load}`}>{n.load}</span>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Where they come from</h3>
        {city.origins.map((o) => (
          <div key={o.station} className="row between">
            <span>{o.station}</span><strong>{o.count}</strong>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Recommendations</h3>
        {city.recommendations.length === 0 && <p className="muted">No action needed.</p>}
        {city.recommendations.map((r, i) => (
          <p key={i}>
            <span className={`badge load-${r.severity}`}>{r.severity}</span> {r.text}
          </p>
        ))}
      </div>
    </div>
  );
}