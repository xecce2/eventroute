import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getCityOverview } from "../api";
import { EVENT_ID } from "../constants";
import { fmt } from "../utils";

function ChartTip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const { time, count } = payload[0].payload;
  return (
    <div className="chart-tip"><b>{count}</b> arriving at {time}</div>
  );
}

export default function CityDashboard() {
  const [city, setCity] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCityOverview(EVENT_ID).then(setCity).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">Error: {error}</p>;
  if (!city) return <div className="panel loading"><span className="spinner" /> Loading the city overview…</div>;

  const data = city.arrivals_by_slot.map((s) => ({ time: fmt(s.slot), count: s.count }));
  const peak = Math.max(0, ...data.map((d) => d.count));
  const maxHub = Math.max(1, ...city.nodes.map((n) => n.peak_count));
  const maxOrigin = Math.max(1, ...city.origins.map((o) => o.count));

  return (
    <div className="city">
      <div className="panel">
        <h3>Arrivals at the entrance <small className="muted">· {city.participants_total} participants, per 15 min</small></h3>
        {/* The chart takes its colour from CSS (currentColor), so the dark theme needs no extra code. */}
        <div style={{ height: 280, color: "var(--brand)" }}>
          <ResponsiveContainer>
            <BarChart data={data} barCategoryGap={3} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid vertical={false} stroke="currentColor" strokeOpacity={0.14} />
              <XAxis dataKey="time" tickLine={false} axisLine={false} tick={{ fill: "var(--ink-3)", fontSize: 12 }} />
              <YAxis tickLine={false} axisLine={false} tick={{ fill: "var(--ink-3)", fontSize: 12 }} allowDecimals={false} />
              <Tooltip content={<ChartTip />} cursor={{ fill: "currentColor", fillOpacity: 0.08 }} />
              <Bar dataKey="count" fill="currentColor" radius={[4, 4, 0, 0]} maxBarSize={44}>
                {data.map((d) => (
                  <Cell key={d.time} fillOpacity={d.count === peak && peak > 0 ? 1 : 0.55} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <small className="muted">
          Forecast for the event day. Synthetic participants, not real people. Those staying overnight are not in the wave.
        </small>
        <details className="table-view">
          <summary>Show as a table</summary>
          <table>
            <thead><tr><th>Time</th><th>Arrivals</th></tr></thead>
            <tbody>
              {data.map((d) => <tr key={d.time}><td>{d.time}</td><td>{d.count}</td></tr>)}
            </tbody>
          </table>
        </details>
      </div>

      <div className="col">
        <div className="panel">
          <h3>Hubs</h3>
          {city.nodes.map((n) => (
            <div key={n.name} className="hub">
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
                <b>{n.name}</b>
                <span className={`badge load-${n.load}`}>{n.load}</span>
              </div>
              <div className="meter" aria-hidden="true"><i style={{ width: `${(n.peak_count / maxHub) * 100}%` }} /></div>
              <small className="muted">
                {n.peak_slot ? `peak ${n.peak_count} people at ${fmt(n.peak_slot)}` : "no arrivals"}
              </small>
            </div>
          ))}
        </div>

        <div className="panel">
          <h3>Where they come from</h3>
          {city.origins.map((o) => (
            <div key={o.station} className="origin">
              <span>{o.station}</span><strong>{o.count}</strong>
              <div className="meter" aria-hidden="true"><i style={{ width: `${(o.count / maxOrigin) * 100}%` }} /></div>
            </div>
          ))}
        </div>
      </div>

      <div className="panel wide">
        <h3>Recommendations</h3>
        {city.recommendations.length === 0 && <p className="muted">No action needed.</p>}
        {city.recommendations.map((r, i) => (
          <div key={i} className={`callout ${r.severity}`}>
            <span className={`badge load-${r.severity}`}>{r.severity}</span>
            <p>{r.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
