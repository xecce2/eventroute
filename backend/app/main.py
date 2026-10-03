from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import city, disruption, events, plan
from app.config import CORS_ORIGINS

app = FastAPI(title="EventRoute API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (events, plan, disruption, city):
    app.include_router(module.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
