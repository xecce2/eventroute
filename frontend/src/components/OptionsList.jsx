import { fmt, probColor } from "../utils";

export default function OptionsList({ options, selectedId, onSelect }) {
  if (!options?.length) return null;

  return (
    <div className="panel">
      <h3>All options ({options.length}), cheapest first</h3>
      <div className="options">
        {options.map((o) => {
          const t = o.train;
          return (
            <div
              key={o.id}
              className={`option ${o.id === selectedId ? "sel" : ""} ${o.overnight_stay ? "overnight" : ""}`}
              onClick={() => onSelect(o.id)}
            >
              <span>{t.mode === "bus" ? "🚌" : "🚆"}</span>
              <span className="time">{fmt(t.dep)} → {fmt(t.arr)}</span>
              <span className="muted">
                {t.category}{t.changes > 0 ? ` · ${t.changes} change${t.changes > 1 ? "s" : ""}` : ""}
              </span>
              <strong>{o.price_pln == null ? "price on site" : `${o.price_pln} zł`}</strong>
              <span style={{ color: probColor(o.p_on_time) }}>{Math.round(o.p_on_time * 100)}%</span>
              {o.overnight_stay && <span className="badge warn">overnight</span>}
              {o.labels.map((l) => <span key={l} className="badge good">{l}</span>)}
            </div>
          );
        })}
      </div>
    </div>
  );
}