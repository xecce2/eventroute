import { fmt } from "../utils";

export default function Timeline({ plan }) {
  const t = plan.train;
  const steps = [
    { time: t.dep, text: `Depart ${t.from} (${t.train})`, strong: true },
    { time: t.arr, text: `Arrive ${t.to}`, late: t.known_delay_min },
    ...plan.local_legs.map((l) => ({
      time: l.dep,
      text:
        l.mode === "walk"
          ? `Walk to ${l.to} (${l.duration_min} min)`
          : `${l.mode === "tram" ? "Tram" : "Bus"} ${l.line ?? ""} to ${l.to} (${l.duration_min} min)`,
    })),
    { time: plan.arrival_at_venue, text: "At the entrance", strong: true },
  ];

  return (
    <div className="panel">
      <h3>Your journey</h3>
      <ol className="timeline">
        {steps.map((s, i) => (
          <li key={i}>
            <b>{fmt(s.time)}</b>
            <span className={s.strong ? "strong" : ""}>{s.text}</span>
            {s.late > 0 && <span className="bad"> +{s.late} min late</span>}
          </li>
        ))}
        <li className="target">
          <b>{fmt(plan.venue_target)}</b>
          <span>Be at the entrance by now</span>
        </li>
      </ol>
    </div>
  );
}
