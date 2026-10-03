import { fmt } from "../utils";

const pct = (p) => `${Math.round(p.p_on_time * 100)}%`;

export default function DisruptionPanel({ before, res }) {
  const after = res.affected_plan;
  const noAlt = !res.plans || res.plans.length === 0;

  return (
    <div className="panel alert">
      <h3>Train delayed</h3>
      {!res.notified && <p className="notice">🔔 {res.message}</p>}
      {res.notified && <p className="notice">📨 Sent to Telegram: {res.message}</p>}

      {after && (
        <table>
          <thead>
            <tr><th></th><th>Before</th><th>Now</th></tr>
          </thead>
          <tbody>
            <tr><td>Chance</td><td>{pct(before)}</td><td className="bad">{pct(after)}</td></tr>
            <tr><td>Buffer</td><td>{before.buffer_min} min</td><td className="bad">{after.buffer_min} min</td></tr>
            <tr><td>At entrance</td><td>{fmt(before.arrival_at_venue)}</td><td className="bad">{fmt(after.arrival_at_venue)}</td></tr>
          </tbody>
        </table>
      )}
      {noAlt && <p className="bad">No alternative route found.</p>}
    </div>
  );
}
