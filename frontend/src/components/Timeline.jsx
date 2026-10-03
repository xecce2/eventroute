import { dayOf, longDate, stamp } from "../utils";

const LEG_ICON = { walk: "🚶", tram: "🚋", bus: "🚌" };

export default function Timeline({ plan }) {
  const t = plan.train;
  const steps = [
    { time: t.dep, icon: t.mode === "bus" ? "🚌" : "🚆", text: `Depart ${t.from} (${t.train})`, strong: true },
    { time: t.arr, icon: "📍", text: `Arrive ${t.to}`, late: t.known_delay_min },
    ...plan.local_legs.map((l) => ({
      time: l.dep,
      icon: LEG_ICON[l.mode] ?? "➡️",
      text:
        l.mode === "walk"
          ? `Walk to ${l.to} (${l.duration_min} min)`
          : `${l.mode === "tram" ? "Tram" : "Bus"} ${l.line ?? ""} to ${l.to} (${l.duration_min} min)`,
    })),
    { time: plan.arrival_at_venue, icon: "🏁", text: "At the entrance", strong: true, last: true },
  ];

  return (
    <div className="panel">
      <h3>Your journey</h3>
      <ol className="timeline">
        {steps.map((s, i) => (
          <li key={i} className={s.last ? "last" : ""}>
            <b>{stamp(s.time, plan.venue_target)}</b>
            <span className="dot" aria-hidden="true">{s.icon}</span>
            <span className={`what ${s.strong ? "strong" : ""}`}>
              {s.text}
              {s.late > 0 && <span className="bad"> +{s.late} min late</span>}
            </span>
          </li>
        ))}
        <li className="target">
          <b>{stamp(plan.venue_target, plan.venue_target)}</b>
          <span className="dot" aria-hidden="true">🎯</span>
          <span className="what">Be at the entrance by now ({longDate(dayOf(plan.venue_target))})</span>
        </li>
      </ol>
    </div>
  );
}
