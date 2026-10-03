import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT_DIR / "data" / "fixtures"

MC_RUNS = int(os.getenv("MC_RUNS", "1000"))
# Pause between replayed SSE statuses, so the search progress is visible in the UI.
SSE_STEP_SEC = float(os.getenv("SSE_STEP_SEC", "0.4"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
