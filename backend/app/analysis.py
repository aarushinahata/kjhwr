"""Core logic: pick the forecast available at decision time, and measure its error.

Assumption (documented in README): day-ahead decisions for delivery day D are made
by CUTOFF_HOUR (default 09:00 UK time) on day D-1. In January UK time == UTC.
"""
import numpy as np
import pandas as pd

DEFAULT_CUTOFF_HOUR = 9


def upsample_forecasts_to_half_hourly(forecasts: pd.DataFrame) -> pd.DataFrame:
    """WINDFOR is hourly but FUELHH is half-hourly (30 min settlement periods).

    Assumption: an hourly forecast starting at HH:00 applies to both HH:00 and HH:30.
    Each row is duplicated with startTime + 30 min. Same publishTime, same value.
    """
    df = forecasts.copy()
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    second = df.copy()
    second["startTime"] = second["startTime"] + pd.Timedelta(minutes=30)
    return pd.concat([df, second], ignore_index=True)


def select_forecast_at_cutoff(forecasts: pd.DataFrame, cutoff_hour: int = DEFAULT_CUTOFF_HOUR) -> pd.DataFrame:
    """For each startTime keep the latest forecast with publishTime <= cutoff on D-1.

    Input columns: startTime, publishTime, generation (tz-aware UTC datetimes).
    Output columns: startTime, publishTime, forecast, horizon_h
    """
    df = forecasts.copy()
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    delivery_day = df["startTime"].dt.floor("D")
    df["cutoff"] = delivery_day - pd.Timedelta(days=1) + pd.Timedelta(hours=cutoff_hour)
    eligible = df[df["publishTime"] <= df["cutoff"]]  # no future information leaks in
    eligible = eligible.sort_values(["startTime", "publishTime"])
    latest = eligible.groupby("startTime", as_index=False).last()
    latest = latest.rename(columns={"generation": "forecast"})
    latest["horizon_h"] = (latest["startTime"] - latest["publishTime"]).dt.total_seconds() / 3600
    return latest[["startTime", "publishTime", "forecast", "horizon_h"]]


def join_with_actuals(selected: pd.DataFrame, actuals: pd.DataFrame) -> pd.DataFrame:
    """Inner-join on startTime. Forecast rows without an actual (or vice versa) are dropped."""
    a = actuals.copy()
    a["startTime"] = pd.to_datetime(a["startTime"], utc=True)
    a = a.drop_duplicates("startTime", keep="last").rename(columns={"generation": "actual"})
    out = selected.merge(a[["startTime", "actual"]], on="startTime", how="inner")
    out["error"] = out["forecast"] - out["actual"]  # + means forecast too high
    out["abs_error"] = out["error"].abs()
    return out


def compute_metrics(joined: pd.DataFrame) -> dict:
    if joined.empty:
        return {"n": 0}
    e, ae = joined["error"], joined["abs_error"]
    nonzero = joined[joined["actual"] > 0]
    mape = float((nonzero["abs_error"] / nonzero["actual"]).mean() * 100) if len(nonzero) else None
    return {
        "n": int(len(joined)),
        "mae": float(ae.mean()),
        "rmse": float(np.sqrt((e ** 2).mean())),
        "bias": float(e.mean()),
        "mape_pct": mape,
        "p50_abs_error": float(ae.quantile(0.50)),
        "p90_abs_error": float(ae.quantile(0.90)),
        "p95_abs_error": float(ae.quantile(0.95)),
        "mean_actual": float(joined["actual"].mean()),
        # Signed error percentiles (error = forecast - actual), used for the asymmetric band
        "err_p05": float(e.quantile(0.05)),
        "err_p95": float(e.quantile(0.95)),
    }


def metrics_by_hour(joined: pd.DataFrame) -> list[dict]:
    g = joined.assign(hour=joined["startTime"].dt.hour).groupby("hour")
    return [
        {"hour": int(h), "mae": float(d["abs_error"].mean()), "bias": float(d["error"].mean())}
        for h, d in g
    ]

HORIZON_BINS = [0, 18, 24, 30, 36, 48, 100]


def metrics_by_horizon(joined: pd.DataFrame) -> list[dict]:
    """Error grouped by how old the forecast was at the deadline (hours before target)."""
    d = joined[joined["horizon_h"] >= 0].copy()
    d["bucket"] = pd.cut(d["horizon_h"], HORIZON_BINS, right=False)
    out = []
    for b, g in d.groupby("bucket", observed=True):
        out.append({
            "from_h": int(b.left), "to_h": int(b.right), "n": int(len(g)),
            "mae": float(g["abs_error"].mean()), "bias": float(g["error"].mean()),
        })
    return out