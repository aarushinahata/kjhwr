"""Download WIND actuals (FUELHH) and forecasts (WINDFOR) from Elexon into data/*.csv.

Run on a machine with internet:  python scripts/fetch_data.py
Chunks requests into 7-day windows because stream endpoints limit the range.
NOTE: verify parameter names against https://bmrs.elexon.co.uk/api-documentation
"""
import datetime as dt
import pathlib
import httpx
import pandas as pd

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
OUT = pathlib.Path(__file__).resolve().parents[1] / "data"
# Forecasts for 1 Jan are published in late Dec, so fetch a buffer on both sides.
START = dt.datetime(2025, 12, 30)
END = dt.datetime(2026, 2, 1)


def chunks(start, end, days=7):
    cur = start
    while cur < end:
        nxt = min(cur + dt.timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def get(client, path, params):
    r = client.get(f"{BASE}/{path}/stream", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    OUT.mkdir(exist_ok=True)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    with httpx.Client() as c:
        actual_rows, fc_rows = [], []
        for s, e in chunks(START, END):
            actual_rows += get(c, "FUELHH", {
                "settlementDateFrom": s.date().isoformat(),
                "settlementDateTo": e.date().isoformat(),
                "fuelType": "WIND",
            })
            fc_rows += get(c, "WINDFOR", {
                "publishDateTimeFrom": s.strftime(fmt),
                "publishDateTimeTo": e.strftime(fmt),
            })
    a = pd.DataFrame(actual_rows)
    a = a[a["fuelType"] == "WIND"][["startTime", "generation"]]
    f = pd.DataFrame(fc_rows)[["startTime", "publishTime", "generation"]]
    a.drop_duplicates().to_csv(OUT / "actuals.csv", index=False)
    f.drop_duplicates().to_csv(OUT / "forecasts.csv", index=False)
    print(f"actuals: {len(a)} rows, forecasts: {len(f)} rows")


if __name__ == "__main__":
    main()
