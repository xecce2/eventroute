import { probColor, sourceBadge } from "../utils";

const LABELS = { safest: "Most reliable", fastest: "Fastest", cheapest: "Cheapest" };

export default function PlanCard({ plan, selected, onSelect }) {
  const t = plan.train;
  const pct = Math.round(plan.p_on_time * 100);
  const late = plan.buffer_min < 0;
  const source = sourceBadge(t.source);

  return (
    <div className={`panel card ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className="badges">
        {plan.labels.map((l) => <span key={l} className="badge good">{LABELS[l] ?? l}</span>)}
        {plan.overnight_stay && <span className="badge warn">Overnight stay needed</span>}
        <span className={`badge ${source.className}`}>{source.text}</span>
      </div>

      <div className="prob">
        <div className="pct" style={{ color: probColor(plan.p_on_time) }}>{pct}%</div>
        <div>
          <div>chance to make it</div>
          <div className={late ? "bad" : ""}>
            {late ? `${-plan.buffer_min} min late` : `${plan.buffer_min} min to spare`}
          </div>
        </div>
      </div>
      <div className="bar">
        <div style={{ width: `${pct}%`, background: probColor(plan.p_on_time) }} />
      </div>

      <h3>
        {t.mode === "bus" ? "🚌" : "🚆"} {t.train} <small>({t.category})</small>
        {t.known_delay_min > 0 && <span className="bad"> +{t.known_delay_min} min</span>}
      </h3>
      <p className="muted">{t.from} → {t.to}</p>
      <p className="muted">{plan.explanation}</p>

      <div className="row between">
        <strong>{plan.price_pln == null ? "price on site" : `${plan.price_pln} zł`}</strong>
        <a className="button" href={plan.buy_url} target="_blank" rel="noreferrer"
           onClick={(e) => e.stopPropagation()}>
          Buy on Koleo
        </a>
      </div>
    </div>
  );
}
