import { useState } from "react";
import { getPlans, simulateDisruption } from "./api";
import RegistrationForm from "./components/RegistrationForm";
import PlanCard from "./components/PlanCard";
import OptionsList from "./components/OptionsList";
import Timeline from "./components/Timeline";
import MapView from "./components/MapView";
import DisruptionPanel from "./components/DisruptionPanel";
import CityDashboard from "./components/CityDashboard";
import "./App.css";

export default function App() {
  const [tab, setTab] = useState("trip");
  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [disruption, setDisruption] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function run(fn) {
    setLoading(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const plans = result?.plans ?? [];
  const options = result?.options ?? [];
  const all = [...plans, ...options];
  const selected = all.find((p) => p.id === selectedId) ?? plans[0] ?? options[0];

  const onPlan = (req) =>
    run(async () => {
      const data = await getPlans(req);
      setResult(data);
      setDisruption(null);
      setSelectedId(data.plans?.[0]?.id ?? data.options?.[0]?.id ?? null);
    });

  const onDelay = () =>
    run(async () => {
      const res = await simulateDisruption(selected.id, 25);
      setDisruption({ before: selected, res });
      setResult({
        ...result,
        plans: res.plans ?? [],
        options: res.options ?? result.options,
      });
      setSelectedId(res.affected_plan?.id ?? selected.id);
    });

  return (
    <div className="app">
      <header>
        <h1>EventRoute</h1>
        <nav>
          <button className={tab === "trip" ? "active" : ""} onClick={() => setTab("trip")}>My trip</button>
          <button className={tab === "city" ? "active" : ""} onClick={() => setTab("city")}>City view</button>
        </nav>
      </header>

      {tab === "city" ? (
        <CityDashboard />
      ) : (
        <>
          <RegistrationForm onSubmit={onPlan} loading={loading} />
          {error && <p className="bad">Error: {error}</p>}

          {result?.fallback_reason && (
            <p className="notice">⚠ Live search failed, showing recorded data ({result.fallback_reason})</p>
          )}
          {result?.status === "no_options" && <p className="bad">No suitable options.</p>}

          {selected && (
            <div className="trip">
              <div className="col">
                {plans.map((p) => (
                  <PlanCard key={p.id} plan={p} selected={p.id === selected.id}
                            onSelect={() => setSelectedId(p.id)} />
                ))}
                <button className="danger" disabled={loading} onClick={onDelay}>
                  Train delayed 25 min (for the selected option)
                </button>
                {disruption && <DisruptionPanel {...disruption} />}
                <OptionsList options={options} selectedId={selected.id} onSelect={setSelectedId} />
              </div>
              <div className="col">
                {selected.overnight_stay && (
                  <p className="notice">
                    ⚠ This option arrives the day before the event. You need a place to stay.
                  </p>
                )}
                <Timeline plan={selected} />
                <MapView plan={selected} />
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}