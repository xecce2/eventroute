from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import city, disruption, events, plan, providers
from app.config import CORS_ORIGINS

app = FastAPI(title="EventRoute API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (events, plan, disruption, city, providers):
    app.include_router(module.router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    # The default answer echoes the rejected `input`; a NaN or Infinity there cannot be
    # written as JSON and turns the 422 into a 500.
    errors = [{k: v for k, v in e.items() if k != "input"} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
