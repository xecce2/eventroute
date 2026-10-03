import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT_DIR / "data" / "fixtures"

# Secrets live in <repo>/.env (git-ignored). Real environment variables win over the file.
load_dotenv(ROOT_DIR / ".env")

# Empty -> no live agent: planning stays on fixtures.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

MC_RUNS = int(os.getenv("MC_RUNS", "1000"))
# Pause between replayed SSE statuses, so the search progress is visible in the UI.
SSE_STEP_SEC = float(os.getenv("SSE_STEP_SEC", "0.4"))
# Vite dev server (5173) and `vite preview` (4173), by name and by IP.
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
).split(",")
