import pathlib
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from .analysis import (DEFAULT_CUTOFF_HOUR, compute_metrics, join_with_actuals,
                                            metrics_by_horizon, metrics_by_hour, select_forecast_at_cutoff,
                       upsample_forecasts_to_half_hourly)

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
app = FastAPI(title="Wind Forecast Decision Tool", version="1.0")


@lru_cache
def load():
    try:
        return pd.read_csv(DATA / "actuals.csv"), pd.read_csv(DATA / "forecasts.csv")
    except FileNotFoundError:
        raise HTTPException(503, "Data missing. Run scripts/fetch_data.py first.")


def january_only(df: pd.DataFrame) -> pd.DataFrame:
    s = df["startTime"]
    return df[(s >= "2026-01-01T00:00:00+00:00") & (s < "2026-02-01T00:00:00+00:00")]


def build(cutoff_hour: int) -> pd.DataFrame:
    actuals, forecasts = load()
    forecasts = upsample_forecasts_to_half_hourly(forecasts)
    sel = select_forecast_at_cutoff(forecasts, cutoff_hour)
    return january_only(join_with_actuals(sel, actuals))


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/decision")
def decision(date: str = Query(..., description="Delivery day, YYYY-MM-DD, in Jan 2026"),
             cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=0, le=23)):
    """Forecast available at decision time for one delivery day, plus actuals."""
    df = build(cutoff_hour)
    day = df[df["startTime"].dt.strftime("%Y-%m-%d") == date]
    if day.empty:
        raise HTTPException(404, "No data for that date (must be within Jan 2026).")
    return {
        "cutoff_hour_utc": cutoff_hour,
        "metrics": compute_metrics(day),
        "points": [
            {"t": r.startTime.isoformat(), "forecast": r.forecast, "actual": r.actual,
             "published": r.publishTime.isoformat()}
            for r in day.itertuples()
        ],
    }


@app.get("/api/v1/metrics")
def metrics(cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=0, le=23)):
    df = build(cutoff_hour)
    return {"cutoff_hour_utc": cutoff_hour, "overall": compute_metrics(df),
            "by_hour": metrics_by_hour(df)}


@app.get("/api/v1/metrics/by-horizon")
def by_horizon(cutoff_hour: int = Query(DEFAULT_CUTOFF_HOUR, ge=0, le=23)):
    """Does error grow when the forecast is older at decision time?"""
    return {"cutoff_hour_utc": cutoff_hour, "buckets": metrics_by_horizon(build(cutoff_hour))}


import os
from fastapi.staticfiles import StaticFiles

# In Docker the built React app is copied to ./static and served from the same server.
STATIC = pathlib.Path(os.getenv("STATIC_DIR", "static"))
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
