import { useEffect, useState } from "react";
import { FALLBACK_EVENT, FALLBACK_STATIONS, EVENT_ID } from "../constants";
import { getEvent, getStations } from "../api";
import { eventTarget, longDate, toArriveBy } from "../utils";

export default function RegistrationForm({ onSubmit, loading }) {
  const [event, setEvent] = useState(FALLBACK_EVENT);
  const [stations, setStations] = useState(FALLBACK_STATIONS);
  const [origin, setOrigin] = useState("Wrocław Główny");
  // The date and time to be at the entrance are the event's own until the user picks others.
  const [pickedDate, setPickedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [budget, setBudget] = useState("");
  const target = eventTarget(event);
  const date = pickedDate ?? target.date;
  const time = pickedTime ?? target.time;

  useEffect(() => {
    getStations(EVENT_ID)
      .then((list) => {
        if (!Array.isArray(list) || list.length === 0) return;
        setStations(list);
        setOrigin((cur) => (list.includes(cur) ? cur : list[0]));
      })
      .catch(() => {}); // keep the fallback list
    getEvent(EVENT_ID)
      .then((loaded) => setEvent(loaded))
      .catch(() => {}); // keep the fallback event
  }, []);

  const ready = Boolean(date && time);

  function submit() {
    if (!ready) return;
    onSubmit({
      origin,
      event_id: EVENT_ID,
      arrive_by: toArriveBy(date, time),
      budget_pln: budget ? Number(budget) : null,
      mode_pref: null,
    });
  }

  return (
    <div className="panel form">
      <div className="event">
        <strong>{event.name}</strong>
        <span>
          {event.venue}
          {ready && ` · be at the entrance by ${time} on ${longDate(date)}`}
        </span>
      </div>
      <label>
        Coming from
        <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
          {stations.map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      <div className="row">
        <label>
          Date
          <input
            type="date"
            value={date}
            onChange={(e) => setPickedDate(e.target.value)}
          />
        </label>
        <label>
          Be at the entrance by
          <input
            type="time"
            value={time}
            onChange={(e) => setPickedTime(e.target.value)}
          />
        </label>
        <label>
          Budget, zł (optional)
          <input type="number" min="1" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </label>
      </div>
      <button className="primary" disabled={loading || !ready} onClick={submit}>
        {loading ? "Searching for trains…" : "Plan my trip"}
      </button>
    </div>
  );
}
