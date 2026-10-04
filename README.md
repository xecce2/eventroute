# OneSearch

You have to be at a venue at 9:30 in another city. Which train do you take, and will you actually make it?

OneSearch answers that. You say where you are coming from and when you need to be at the door. It finds the trains and buses, works backwards from your deadline through the tram and the walk, and tells you the chance of arriving on time for each option. If your train runs late, it replans and lets you know.

The organiser and the city get something out of it too: once people have plans, you can see when and where they will arrive, and where the trams will be overloaded.

We built this at HackYeah 2026 in the SmartCity track. The demo plans trips to Tauron Arena Kraków from Wrocław, Warszawa, Poznań and Katowice.

## How it works

The planner starts from the moment you need to be at the entrance and goes backwards. It takes the walk from the tram stop, the tram itself, the walk from the platform, and ends up with the latest train that still works. The tram part uses the real Kraków timetable for lines 15 and 16, so if you reach the stop at 08:23 and the next tram is at 08:37, the plan says 08:37.

Then it runs a thousand simulated trips for every option, with random train delays and walking times. The share of trips that arrive in time is the percentage you see on the card. A delayed train that misses its tram waits for the next one in the simulation, exactly as you would.

You get up to three cards (the safest, the fastest and the cheapest option) and the full list below them. Each one links to the carrier's site. You buy the ticket yourself; OneSearch never pays for anything and never logs in anywhere.

The train data comes from Koleo. In live mode the app opens the Koleo search page in a browser and reads the results with ordinary code. Gemini is there only as a backup reader in case Koleo changes its page layout. Whatever comes back is checked by a validator before you see it. If the live search fails, the app uses real results we recorded earlier and tells you so, including why.

## Getting it running

You need Git, Python 3.11 or newer, and Node.js 20 or newer. The commands below are for Windows PowerShell; there is a note for macOS and Linux at the end of this section.

Clone the project:

```
git clone https://github.com/xecce2/eventroute.git
cd eventroute
```

Create the two config files:

```
Copy-Item .env.example .env
Set-Content frontend\.env.local "VITE_DEFAULT_DATE=2026-10-11"
```

The second line makes the form open on 11 October 2026, a date we have recorded timetables for.

Now start the backend in one terminal. The first two commands after `cd` are only needed the first time:

```
cd backend
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

When you see `Uvicorn running on http://127.0.0.1:8000`, open http://localhost:8000/api/health. It should say `{"status":"ok"}`.

Start the frontend in a second terminal (again, `npm install` only the first time):

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Make sure the port really is 5173. If Vite picked 5174 because something else was using 5173, the app will not reach the backend; close the old process and start again.

To see that everything works, pick Wrocław Główny, keep 11 October and 09:30, and plan the trip. You should get the IC at 05:10 with about a 99% chance and the FlixBus at 03:51 with about 87%. Select the FlixBus and delay it by 25 minutes: it misses its tram, the chance drops to 0%, and the app suggests the IC instead.

On macOS and Linux, use `python3` instead of `py`, `.venv/bin/python` instead of `.venv\Scripts\python`, `cp .env.example .env` to copy the config, and `echo "VITE_DEFAULT_DATE=2026-10-11" > frontend/.env.local` for the second file.

## Recorded data or live search

Out of the box the app runs on recorded data. That is the `TRAIN_PROVIDER=fixture` line in `.env`. These are real Koleo results we saved for 3–4 and 10–11 October 2026. This mode needs no internet and no keys, which is why it is the default, but it is not a live search: pick any other date and you will get an empty list.

For a live search, change that line to `TRAIN_PROVIDER=koleo`. You will also need an internet connection, Google Chrome installed, and a Gemini key in `GEMINI_API_KEY`. Without the key the app quietly stays on recorded data. Pick a date in the future, because Koleo only shows trains that have not left yet. A live search takes 20 to 40 seconds.

Restart the backend after changing `.env`. If you are not sure which mode is active, http://localhost:8000/api/providers/status will tell you.

Two more settings in `.env` are optional. `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` turn on delay notifications in Telegram; the person receiving them has to press Start in the bot first. Without them the message simply appears in the app. `DEMO_NOW` freezes the clock at a moment of your choice, for example `2026-10-04T03:00:00+02:00`, which is useful for showing the 4 October timetables after that day has passed. Leave it empty otherwise, and do not use it together with live search.

## When something goes wrong

If every city says "No suitable options", the date you picked has no trains left. Go back to 11 October, or switch to live search with a future date.

"Failed to fetch" means the frontend cannot reach the backend. Either the backend is not running or the frontend is on the wrong port.

If the backend complains about a time zone on startup, the dependencies did not install properly. Run the `pip install` line again; Windows needs the `tzdata` package from it.

If PowerShell does not recognise `uvicorn` or `pytest`, run them the way this page shows, through `.venv\Scripts\python -m`.

If the delay button answers with a 404, the backend was restarted in the meantime. It keeps plans in memory only, so plan the trip again.

A grey map means there is no internet. The background tiles come from OpenStreetMap; the route and the markers are still drawn.

## Tests

```
cd backend
.venv\Scripts\python -m pytest
```

The tests never touch the network or send Telegram messages, and they do not depend on your `.env` or on today's date.

## Where things are

The backend lives in `backend/`: the planner, the simulation, the Koleo reader, the validator, the Telegram notifier and the city overview. `backend/scripts/` has two helpers, one that records Koleo results into fixtures and one that refreshes the example API responses.

The frontend is in `frontend/`: the form, the plan cards, the map, the timeline, the delay view and the city view.

`data/fixtures/` holds everything recorded: the timetables, the event, the local route with its tram timetable, and the capacity of the transport nodes.

`docs/` has a brief for frontend work and real API responses in `docs/api-examples/`. The interactive API documentation is at http://localhost:8000/docs while the backend runs.

## What is real and what is not

The train and bus options are real Koleo results, either recorded or read live. The tram timetable is from the ZTP Kraków GTFS feed, and the walking routes and map are from OpenStreetMap.

The delay statistics per train type are our own estimates, and so are the capacities of the station and the check-in desks. The 420 participants in the city view are generated; there is no personal data anywhere in the project.

This is a demo, and it has limits. It knows one destination and one route through Kraków. Recorded data covers two weekends. While a live search runs, you see a spinner rather than real progress. The short explanation on each card is filled in from a template. In a real product the Koleo reader would be replaced by a partner API from the carriers.
