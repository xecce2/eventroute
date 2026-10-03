import { fmtPrice, probColor, stamp } from "../utils";

export default function OptionsList({ options, selectedId, onSelect }) {
  if (!options?.length) return null;

  return (
    <div className="panel">
      <h3>All options ({options.length}) <small className="muted">cheapest first</small></h3>
      <div className="options">
        {options.map((o) => {
          const t = o.train;
          const price = fmtPrice(o.price_pln);
          return (
            <div
              key={o.id}
              className={`option ${o.id === selectedId ? "sel" : ""} ${o.overnight_stay ? "overnight" : ""}`}
              onClick={() => onSelect(o.id)}
            >
              <span aria-hidden="true">{t.mode === "bus" ? "🚌" : "🚆"}</span>
              <span className="time">{stamp(t.dep, o.venue_target)} → {stamp(t.arr, o.venue_target)}</span>
              <span className="chip cat">
                {t.category}{t.changes > 0 ? ` · ${t.changes} change${t.changes > 1 ? "s" : ""}` : ""}
              </span>
              <strong>{price == null ? "price on site" : `${price} zł`}</strong>
              <span className="prob" style={{ color: probColor(o.p_on_time) }}>{Math.round(o.p_on_time * 100)}%</span>
              <div className="tags">
                {o.overnight_stay && <span className="badge warn">🛏 overnight</span>}
                {o.labels.map((l) => <span key={l} className="badge good">{l}</span>)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
