import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from src.garmin_client import GarminClient
from src.history_db import HistoryDB
from src.ingestor import Ingestor
from api import services

app = FastAPI(title="Garmin AI Coach")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = None


def get_client() -> GarminClient:
    global _client
    if _client is None:
        _client = GarminClient()
    return _client


_db = None


def get_db() -> HistoryDB:
    global _db
    if _db is None:
        _db = HistoryDB()
    return _db


def _safe(fn, *, code: int):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — devolve erro estruturado ao frontend
        return JSONResponse(status_code=code, content={"erro": str(e)})


@app.get("/api/today")
def today():
    return _safe(lambda: services.build_today(get_client(), get_db()), code=503)


@app.post("/api/plan")
def plan():
    return _safe(lambda: services.build_plan(get_client(), get_db()), code=502)


@app.get("/api/plan")
def plan_status():
    return _safe(lambda: services.build_plan_status(get_db()), code=503)


@app.get("/api/data")
def data():
    return _safe(lambda: services.build_data(get_client()), code=503)


@app.get("/api/profile")
def profile():
    path = Path("athlete_profile.json")
    if not path.exists():
        return JSONResponse(status_code=404, content={"erro": "athlete_profile.json não encontrado"})
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/trends")
def trends(period: int = 30):
    return _safe(lambda: services.build_trends(get_db(), period), code=503)


@app.get("/api/activities")
def activities(period: int = 30):
    return _safe(lambda: services.build_activities(get_db(), period), code=503)


@app.get("/api/activity/{activity_id}")
def activity_detail(activity_id: int):
    return _safe(lambda: services.build_activity_detail(get_db(), get_client(), activity_id), code=503)


@app.post("/api/sync")
def sync():
    def _run():
        Ingestor(get_client(), get_db()).sync_today()
        return {"ok": True}
    return _safe(_run, code=503)


# Serve build React em prod, se existir (montado por último pra não capturar /api).
_dist = Path("web/dist")
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")
