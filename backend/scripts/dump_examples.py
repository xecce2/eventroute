"""Write real API responses to docs/api-examples/ so the frontend mocks match the backend exactly.

Run from backend/:  python scripts/dump_examples.py
Uses fixtures only, no network. Demo flow: Wrocław -> 3 cards -> fastest card delayed by 25 min.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.config import ROOT_DIR  # noqa: E402
from app.main import app  # noqa: E402

OUT_DIR = ROOT_DIR / "docs" / "api-examples"
EVENT_ID = "ev_hackyeah2026"
# Before every recorded departure, so the examples show the full list on any day.
EXAMPLES_NOW = datetime.fromisoformat("2026-10-03T12:00:00+02:00")


def main() -> None:
    config.DEMO_NOW = EXAMPLES_NOW
    config.TELEGRAM_BOT_TOKEN = ""  # the disruption example must not send a real message
    client = TestClient(app)

    def get(path: str) -> dict | list:
        r = client.get(path)
        r.raise_for_status()
        return r.json()

    def post(path: str, body: dict) -> dict:
        r = client.post(path, json=body)
        r.raise_for_status()
        return r.json()

    plan = post("/api/plan", {"origin": "Wrocław Główny", "event_id": EVENT_ID})
    fastest = next(p for p in plan["plans"] if "fastest" in p["labels"])
    examples = {
        "event": get(f"/api/events/{EVENT_ID}"),
        "stations": get(f"/api/events/{EVENT_ID}/stations"),
        "plan": plan,
        "disruption": post("/api/simulate/disruption", {"plan_id": fastest["id"], "train_delay_min": 25}),
        "city_overview": get(f"/api/city/overview?event_id={EVENT_ID}"),
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in examples.items():
        path = OUT_DIR / f"{name}.json"
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
