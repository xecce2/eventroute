import { useState } from "react";
import { getPlans, simulateDisruption, USE_MOCKS } from "./api";
import RegistrationForm from "./components/RegistrationForm";
import PlanCard from "./components/PlanCard";
import OptionsList from "./components/OptionsList";
import Timeline from "./components/Timeline";
import MapView from "./components/MapView";
import DisruptionPanel from "./components/DisruptionPanel";
import CityDashboard from "./components/CityDashboard";
import "./App.css";

function Logo() {
  return (
    <div className="logo" aria-hidden="true">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
           strokeLinecap="round" strokeLinejoin="round">
        <circle cx="5" cy="18" r="2.2" />
        <circle cx="19" cy="6" r="2.2" />
        <path d="M7 18h6a3 3 0 0 0 0-6h-2a3 3 0 0 1 0-6h6" />
      </svg>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("trip");
  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [disruption, setDisruption] = useState(null);
  const [busy, setBusy] = useState(null); // "plan" | "delay" | null
  const [error, setError] = useState(null);
  const loading = busy !== null;

  async function run(kind, fn) {
    setBusy(kind);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  }

  const plans = result?.plans ?? [];
  const options = result?.options ?? [];
  const affected = disruption?.res?.affected_plan;
  // The affected plan is kept in the search list: after a delay the recalculated lists
  // may not contain it (it can become too late), and it must stay selectable.
  const all = [...plans, ...options, ...(affected ? [affected] : [])];
  const selected = all.find((p) => p.id === selectedId) ?? plans[0] ?? options[0];

  const onPlan = (req) =>
    run("plan", async () => {
      const data = await getPlans(req);
      setResult(data);
      setDisruption(null);
      setSelectedId(data.plans?.[0]?.id ?? data.options?.[0]?.id ?? null);
    });

  const onDelay = () =>
    run("delay", async () => {
      const res = await simulateDisruption(selected.id, 25);
      setDisruption({ before: selected, res });
      const next = {
        ...result,
        plans: res.plans ?? [],
        options: res.options ?? result.options,
      };
      setResult(next);
      // The backend gives the same train a new plan id in the recalculated lists,
      // so the delayed plan is found by train id, not by plan id.
      const delayed = res.affected_plan;
      const same = delayed && [...next.plans, ...next.options].find((p) => p.train.id === delayed.train.id);
      setSelectedId(same?.id ?? delayed?.id ?? selected.id);
    });

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <Logo />
          <div>
            <div className="brand-name">EventRoute</div>
            <div className="brand-tag">Plan the way to the event, backwards from the entrance</div>
          </div>
        </div>
        <nav className="tabs">
          <button className={tab === "trip" ? "active" : ""} onClick={() => setTab("trip")}>My trip</button>
          <button className={tab === "city" ? "active" : ""} onClick={() => setTab("city")}>City view</button>
        </nav>
      </header>

      {USE_MOCKS && (
        <p className="mock-banner">
          MOCK DATA: the trains, prices and routes below are invented and not from the backend.
        </p>
      )}

      {tab === "city" ? (
        <CityDashboard />
      ) : (
        <div className="col">
          <RegistrationForm onSubmit={onPlan} loading={loading} />
          {error && <p className="error">Error: {error}</p>}

          {busy === "plan" && !USE_MOCKS && (
            <div className="panel loading">
              <span className="spinner" />
              <div>
                <b>Reading the live timetable…</b>
                <div className="muted">A new date or time can take up to a minute; the same search again is instant.</div>
              </div>
            </div>
          )}

          {result?.fallback_reason && (
            <p className="notice">⚠ Live search failed, showing recorded data ({result.fallback_reason})</p>
          )}
          {result?.status === "no_options" && <p className="error">No suitable options.</p>}

          {selected && (
            <div className="trip">
              <div className="col">
                {plans.map((p) => (
                  <PlanCard key={p.id} plan={p} selected={p.id === selected.id}
                            onSelect={() => setSelectedId(p.id)} />
                ))}
                <button className="danger" disabled={loading} onClick={onDelay}>
                  ⏱ Train delayed 25 min (for the selected option)
                </button>
                {disruption && <DisruptionPanel {...disruption} />}
                <OptionsList options={options} selectedId={selected.id} onSelect={setSelectedId} />
              </div>
              <div className="col sticky">
                {selected.overnight_stay && (
                  <p className="notice">
                    🛏 This option arrives the day before. You need a place to stay.
                  </p>
                )}
                <Timeline plan={selected} />
                <MapView plan={selected} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
