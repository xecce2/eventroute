import { stamp } from "../utils";

const pct = (p) => `${Math.round(p.p_on_time * 100)}%`;

function Metric({ label, was, now }) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className="was">{was}</div>
      <div className="now">{now}</div>
    </div>
  );
}

export default function DisruptionPanel({ before, res }) {
  const after = res.affected_plan;
  // The delayed train itself is in the recalculated list; only another train is an alternative.
  const alternatives = (res.plans ?? []).filter((p) => p.train.id !== after?.train.id);

  return (
    <div className="panel alert">
      <h3>⏱ Train delayed</h3>
      <div className="bubble">
        <span aria-hidden="true">{res.notified ? "📨" : "🔔"}</span>
        <span>{res.notified ? "Sent to Telegram: " : ""}{res.message}</span>
      </div>

      {after && (
        <div className="compare">
          <Metric label="Chance" was={pct(before)} now={pct(after)} />
          <Metric label="Spare time" was={`${before.buffer_min} min`} now={`${after.buffer_min} min`} />
          <Metric
            label="At the entrance"
            was={stamp(before.arrival_at_venue, before.venue_target)}
            now={stamp(after.arrival_at_venue, after.venue_target)}
          />
        </div>
      )}
      {alternatives.length === 0 && <p className="bad" style={{ marginTop: 12 }}>No alternative route found.</p>}
    </div>
  );
}
