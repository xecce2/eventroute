import { useEffect, useState } from "react";
import { DEFAULT_DATE, FALLBACK_EVENT, FALLBACK_STATIONS, EVENT_ID } from "../constants";
import { getEvent, getStations } from "../api";
import { eventTarget, longDate, toArriveBy, warsawDateTime } from "../utils";

export default function RegistrationForm({ onSubmit, loading }) {
  const [event, setEvent] = useState(FALLBACK_EVENT);
  const [stations, setStations] = useState(FALLBACK_STATIONS);
  const [origin, setOrigin] = useState("Wrocław Główny");
  // The date and time to be at the entrance are the event's own until the user picks others.
  const [pickedDate, setPickedDate] = useState(null);
  const [pickedTime, setPickedTime] = useState(null);
  const [budget, setBudget] = useState("");
  const target = eventTarget(event);
  const eventStart = warsawDateTime(Date.parse(event.start));
  const date = pickedDate ?? DEFAULT_DATE ?? target.date;
  const time = pickedTime ?? target.time;
  const onEventDay = date === eventStart.date;

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

  function submit(e) {
    e.preventDefault();
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
    <form className="panel form" onSubmit={submit}>
      <div className="event">
        {/* The event's name and date are shown only on the event's own day: on any other day the
            event is not happening, so the card names just the place. */}
        <strong>{onEventDay ? `${event.name} · ${event.venue}` : event.venue}</strong>
        {onEventDay && <span>Event: {longDate(eventStart.date)}, {eventStart.time}</span>}
        {ready && <span>Your trip: be at the entrance by {time} on {longDate(date)}</span>}
        {ready && !onEventDay && <span className="muted">ⓘ Live timetable for the day you chose</span>}
      </div>
      <div className="fields">
        <label>
          Coming from
          <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
            {stations.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>
          Date
          <input type="date" value={date} onChange={(e) => setPickedDate(e.target.value)} />
        </label>
        <label>
          Be at the entrance by
          <input type="time" value={time} onChange={(e) => setPickedTime(e.target.value)} />
        </label>
        <label>
          Budget, zł (optional)
          <input type="number" min="1" placeholder="no limit" value={budget} onChange={(e) => setBudget(e.target.value)} />
        </label>
        <button className="primary" type="submit" disabled={loading || !ready}>
          {loading ? <><span className="spinner" /> Searching…</> : "Plan my trip"}
        </button>
      </div>
    </form>
  );
}
