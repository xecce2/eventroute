import ProbRing from "./ProbRing";
import { fmtDuration, fmtPrice, sourceBadge, stamp } from "../utils";

const LABELS = {
  safest: { className: "good", text: "🛡 Most reliable" },
  fastest: { className: "fast", text: "⚡ Fastest" },
  cheapest: { className: "cheap", text: "💰 Cheapest" },
};

export default function PlanCard({ plan, selected, onSelect }) {
  const t = plan.train;
  const late = plan.buffer_min < 0;
  const spare = late ? "bad" : plan.buffer_min < 20 ? "warn" : "good";
  const source = sourceBadge(t.source);
  const price = fmtPrice(plan.price_pln);

  return (
    <div className={`panel card ${selected ? "selected" : ""}`} onClick={onSelect}>
      <div className="badges">
        {plan.labels.map((l) => (
          <span key={l} className={`badge ${LABELS[l]?.className ?? ""}`}>{LABELS[l]?.text ?? l}</span>
        ))}
        {plan.overnight_stay && <span className="badge warn">🛏 Overnight stay needed</span>}
        <span className={`badge ${source.className}`}>{source.text}</span>
      </div>

      <div className="card-main">
        <ProbRing value={plan.p_on_time} />
        <div>
          <div className="leave">Depart {t.from}</div>
          <div className="depart">
            {stamp(t.dep, plan.venue_target)} <small>{t.mode === "bus" ? "🚌" : "🚆"} {t.train}</small>
          </div>
          <div className="route">→ {t.to} at {stamp(t.arr, plan.venue_target)} · {fmtDuration(t.dep, t.arr)}</div>
          <div className="chips">
            <span className={`chip ${spare}`}>
              {late ? `${-plan.buffer_min} min late` : `${plan.buffer_min} min to spare`}
            </span>
            <span className="chip">{t.category}</span>
            {t.changes > 0 && <span className="chip warn">{t.changes} change{t.changes > 1 ? "s" : ""}</span>}
            {t.known_delay_min > 0 && <span className="chip bad">+{t.known_delay_min} min delay</span>}
          </div>
        </div>
      </div>

      <p className="explain">{plan.explanation}</p>

      <div className="card-foot">
        <span className="price">
          {price == null ? <small>price on site</small> : <>{price} <small>zł</small></>}
        </span>
        <a className="button" href={plan.buy_url} target="_blank" rel="noreferrer"
           onClick={(e) => e.stopPropagation()}>
          Buy on Koleo ↗
        </a>
      </div>
    </div>
  );
}
