import { probColor } from "../utils";

const R = 38;
const CIRCUMFERENCE = 2 * Math.PI * R;

// The chance of arriving on time as a ring. The number and the words carry the meaning,
// the colour only repeats it (green from 90%, amber from 70%, red below).
export default function ProbRing({ value }) {
  const pct = Math.round(value * 100);
  return (
    <div className="ring" role="img" aria-label={`${pct}% chance to arrive on time`}>
      <svg viewBox="0 0 92 92" aria-hidden="true">
        <circle className="track" cx="46" cy="46" r={R} fill="none" strokeWidth="9" />
        <circle
          className="value" cx="46" cy="46" r={R} fill="none" strokeWidth="9" strokeLinecap="round"
          style={{ stroke: probColor(value) }}
          strokeDasharray={CIRCUMFERENCE} strokeDashoffset={CIRCUMFERENCE * (1 - value)}
        />
      </svg>
      <div className="num"><b>{pct}%</b><small>on time</small></div>
    </div>
  );
}
