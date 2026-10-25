# Wind forecast at decision time

A small web app for a day-ahead power buying team. For any delivery day in January 2026 it shows:

1. The wind generation forecast that was actually available when the day-ahead purchase had to be decided.
2. How accurate those forecasts were against actual generation, with the error quantified.

Data: national-level wind only, from Elexon BMRS (`WINDFOR` forecasts, `FUELHH` actuals, `fuelType = WIND`).

**Live app:** <<PASTE DEPLOYED LINK HERE>>

## Key decisions and assumptions

- **Decision deadline.** Day-ahead purchases for delivery day D are decided on day D-1. The app uses 09:00 UTC on D-1 as the deadline (UK time equals UTC in January). This is an assumption, not an Elexon value, so it can be changed in the UI.
- **Forecast selection.** For each half-hour of day D, the app takes the forecast with the latest `publishTime` that is at or before the deadline. Forecasts published after the deadline are never used, because the buyer could not have seen them.
- **Resolution mismatch.** `WINDFOR` is hourly and `FUELHH` is half-hourly. Each hourly forecast is applied to both half-hours of its hour. Actuals stay at their native 30-minute resolution.
- **Error definition.** `error = forecast - actual`. A positive value means the forecast was too high.
- **Data window.** Forecasts for early January are published in late December, so the fetch script downloads a buffer around January. Metrics use only target times in January 2026.
- **Demand.** Demand data was out of scope. The "how much to buy" box takes one flat demand number from the user and subtracts forecast wind.
- **Band on the chart.** The shaded band is the 5th to 95th percentile of the signed January error applied to the forecast. It leans downward because the forecast ran high more often than low.

## What the data showed (January 2026, 09:00 UTC deadline)

These are observations from one month of data, not explanations.

- All 1,488 half-hours of January had a forecast available before the deadline.
- Average miss was about 2,145 MW and the bias was about +1,852 MW, meaning the forecast was on average higher than actual generation.
- 90th percentile of absolute error was about 4,275 MW and the 95th percentile about 5,341 MW.
- Error did not clearly grow with forecast age. Most of the error was one-sided (bias), not random.

## Run with Docker

```bash
docker compose up --build
```

Open http://localhost:8000. The React build is served by the FastAPI server in the same container.

## Run locally without Docker

Backend (PowerShell shown; use `source venv/bin/activate` on macOS/Linux):

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend, in a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The dev server proxies `/api` to port 8000.

## Refresh the data

The CSV snapshot used by the app is committed in `backend/data/`. To download it again from Elexon:

```powershell
cd backend
python scripts/fetch_data.py
python scripts/inspect_data.py
```

`inspect_data.py` prints row counts, date ranges, forecast horizons and checks that every January hour has a forecast before the deadline.

## Tests

```powershell
cd backend
pytest
```

Tests cover the deadline logic (latest forecast before the deadline, nothing after it, exact-cutoff case, duplicates, unsorted input, forecasts published after their target time), hourly to half-hourly conversion, missing actuals, metric values and sign convention, and horizon buckets. GitHub Actions runs the backend tests and the frontend build on every push.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/health` | Health check |
| `GET /api/v1/decision?date=2026-01-15&cutoff_hour=9` | Forecast at deadline, actuals and metrics for one delivery day |
| `GET /api/v1/metrics?cutoff_hour=9` | January-wide metrics and error by hour of day |
| `GET /api/v1/metrics/by-horizon?cutoff_hour=9` | Error grouped by forecast age at the deadline |

Interactive docs are at `/docs` when the server is running.

## Files and directories

```
.
├── Dockerfile                 Builds the React app, then serves it from FastAPI
├── docker-compose.yml         One-command start
├── .github/workflows/ci.yml   Backend tests and frontend build on every push
├── backend/
│   ├── app/
│   │   ├── analysis.py        Forecast selection, joins, metrics (core logic)
│   │   └── main.py            FastAPI endpoints, serves the built frontend
│   ├── scripts/
│   │   ├── fetch_data.py      Downloads actuals and forecasts from Elexon
│   │   └── inspect_data.py    Data sanity checks
│   ├── tests/                 pytest tests for the logic above
│   ├── data/                  actuals.csv and forecasts.csv snapshot
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.tsx            Dashboard: day chart, metrics, demand box, error charts
    │   ├── api.ts             Typed API client
    │   ├── main.tsx
    │   └── styles.css
    ├── package.json
    └── vite.config.ts         Dev proxy to the backend
```

## Limitations and next steps

- The deadline is an assumption. The real gate closure of the GB day-ahead auctions should be confirmed with the client.
- One month of data is too little to separate a genuine systematic bias from a month-specific pattern.
- No demand data, so the purchase figure uses one flat user-entered number.
- The app reads a data snapshot. A scheduled job to refresh it from Elexon would be the next step.
- Metrics are computed on each request. This is fast for one month, but caching would be needed for longer periods.

## AI usage

AI tools were used to build this project. I used Claude (Anthropic) as an assistant to plan the approach, generate code, and tests. I set up the project on my machine, downloaded the real Elexon data, inspected it, ran the tests, ran the app locally and in Docker, and checked the results against the data. Design choices such as the deadline assumption, the hourly to half-hourly handling and the asymmetric error band were discussed with the assistant and reviewed by me.
