"""Sanity-check the downloaded CSVs. Run: python scripts/inspect_data.py"""
import pathlib
import pandas as pd

D = pathlib.Path(__file__).resolve().parents[1] / "data"
a = pd.read_csv(D / "actuals.csv", parse_dates=["startTime", ], date_format="ISO8601")
f = pd.read_csv(D / "forecasts.csv", parse_dates=["startTime", "publishTime"], date_format="ISO8601")

print("ACTUALS  rows:", len(a), "| unique startTime:", a.startTime.nunique())
print("  range:", a.startTime.min(), "->", a.startTime.max())
print("  step (min):", a.startTime.sort_values().drop_duplicates().diff().dt.total_seconds().div(60).value_counts().head(3).to_dict())

print("FORECASTS rows:", len(f), "| unique startTime:", f.startTime.nunique(), "| unique publishTime:", f.publishTime.nunique())
print("  startTime range:", f.startTime.min(), "->", f.startTime.max())
print("  publishTime range:", f.publishTime.min(), "->", f.publishTime.max())
print("  forecasts per startTime (median):", f.groupby("startTime").size().median())
h = (f.startTime - f.publishTime).dt.total_seconds() / 3600
print("  horizon hours: min", round(h.min(), 1), "median", round(h.median(), 1), "max", round(h.max(), 1))
print("  rows published AFTER their target time:", int((h < 0).sum()))

jan = f[(f.startTime >= "2026-01-01T00:00:00Z") & (f.startTime < "2026-02-01T00:00:00Z")]
cut = jan.startTime.dt.floor("D") - pd.Timedelta(days=1) + pd.Timedelta(hours=9)
ok = jan[jan.publishTime <= cut]
print("Jan target hours with >=1 forecast before cutoff:", ok.startTime.nunique(), "of", jan.startTime.nunique())
