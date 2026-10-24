import { useEffect, useMemo, useState } from "react";
import {
  Area,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  DecisionResponse,
  HorizonResponse,
  MetricsResponse,
  fetchDecision,
  fetchHorizon,
  fetchMetrics,
} from "./api";

const mw = (v?: number | null) =>
  v == null ? "n/a" : `${Math.round(v).toLocaleString()} MW`;
const signed = (v: number) =>
  `${v >= 0 ? "+" : "−"}${Math.abs(Math.round(v)).toLocaleString()} MW`;
const hhmm = (iso: string) => iso.slice(11, 16);
const nice = (iso: string) =>
  new Date(iso).toLocaleString("en-GB", {
    timeZone: "UTC",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });

export default function App() {
  const [date, setDate] = useState("2026-01-15");
  const [cutoff, setCutoff] = useState(9);
  const [demand, setDemand] = useState("");
  const [day, setDay] = useState<DecisionResponse | null>(null);
  const [overall, setOverall] = useState<MetricsResponse | null>(null);
  const [horizon, setHorizon] = useState<HorizonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchDecision(date, cutoff),
      fetchMetrics(cutoff),
      fetchHorizon(cutoff),
    ])
      .then(([d, m, h]) => {
        if (alive) {
          setDay(d);
          setOverall(m);
          setHorizon(h);
        }
      })
      .catch((e: Error) => {
        if (alive) {
          setError(e.message);
          setDay(null);
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [date, cutoff]);

  // error = forecast - actual, so actual lies between forecast - err_p95 and forecast - err_p05
  const errLow = overall?.overall.err_p05 ?? 0;
  const errHigh = overall?.overall.err_p95 ?? 0;

  const chartData = useMemo(
    () =>
      (day?.points ?? []).map((p) => ({
        time: hhmm(p.t),
        forecast: p.forecast,
        actual: p.actual,
        band: [
          Math.max(0, p.forecast - errHigh),
          Math.max(0, p.forecast - errLow),
        ] as [number, number],
      })),
    [day, errLow, errHigh],
  );

  const meanForecast =
    day && day.points.length
      ? day.points.reduce((s, p) => s + p.forecast, 0) / day.points.length
      : 0;
  const demandNum = Number(demand);
  const hasDemand = demand !== "" && !Number.isNaN(demandNum);
  const published = day
    ? Array.from(new Set(day.points.map((p) => p.published))).sort()
    : [];
  const publishedText =
    published.length === 0
      ? ""
      : published.length === 1
        ? `Forecast published ${nice(published[0])} UTC.`
        : `Forecasts published between ${nice(published[0])} and ${nice(published[published.length - 1])} UTC.`;

  const buy = demandNum - meanForecast;
  const buyWorst = demandNum - meanForecast + errHigh;

  return (
    <div className="page">
      <header className="top">
        <div>
          <h1>Wind forecast at decision time</h1>
          <p className="sub">
            For each half-hour of the delivery day, the latest forecast
            published before the day-ahead deadline, compared with what the wind
            actually produced.
          </p>
        </div>
        <div className="controls">
          <label>
            Delivery day
            <input
              type="date"
              value={date}
              min="2026-01-01"
              max="2026-01-31"
              onChange={(e) => e.target.value && setDate(e.target.value)}
            />
          </label>
          <label>
            Deadline on the day before (UTC hour)
            <select
              value={cutoff}
              onChange={(e) => setCutoff(Number(e.target.value))}
            >
              {Array.from({ length: 24 }, (_, h) => (
                <option key={h} value={h}>
                  {String(h).padStart(2, "0")}:00
                </option>
              ))}
            </select>
          </label>
        </div>
      </header>

      {error && <div className="notice error">{error}</div>}
      {loading && !day && <div className="notice">Loading data…</div>}

      {day && (
        <>
          <section className="panel">
            <h2>Forecast and actual wind generation, {date}</h2>
            <p className="hint">
              {publishedText} The shaded band shows where actual wind landed in
              90% of January cases: the forecast {signed(-errHigh)} to{" "}
              {signed(-errLow)}.
              {errHigh > 0 &&
                " The forecast has run high more often than low, so the band leans downward."}
            </p>
            <div className="chart">
              <ResponsiveContainer width="100%" height={340}>
                <ComposedChart
                  data={chartData}
                  margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="time" interval={5} tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v) => `${v / 1000}k`}
                    width={44}
                    label={{
                      value: "MW",
                      angle: -90,
                      position: "insideLeft",
                      fontSize: 12,
                    }}
                  />
                  <Tooltip
                    formatter={(v: number | number[], name: string) =>
                      Array.isArray(v)
                        ? [
                            `${Math.round(v[0])} to ${Math.round(v[1])} MW`,
                            name,
                          ]
                        : [`${Math.round(v)} MW`, name]
                    }
                  />
                  <Area
                    dataKey="band"
                    name="Likely range (90%)"
                    stroke="none"
                    fill="var(--forecast)"
                    fillOpacity={0.14}
                  />
                  <Line
                    dataKey="forecast"
                    name="Forecast (at deadline)"
                    stroke="var(--forecast)"
                    strokeWidth={2.5}
                    dot={false}
                  />
                  <Line
                    dataKey="actual"
                    name="Actual"
                    stroke="var(--actual)"
                    strokeWidth={2}
                    dot={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="legend">
              <span>
                <i style={{ background: "var(--forecast)" }} />
                Forecast available at the deadline
              </span>
              <span>
                <i style={{ background: "var(--actual)" }} />
                Actual generation
              </span>
            </div>
          </section>

          <section className="grid">
            <div className="panel">
              <h2>How wrong was the forecast on {date}?</h2>
              <dl className="stats">
                <Stat
                  label="Average miss"
                  value={mw(day.metrics.mae)}
                  help="Typical gap between forecast and actual"
                />
                <Stat
                  label="Bias"
                  value={mw(day.metrics.bias)}
                  help={
                    (day.metrics.bias ?? 0) >= 0
                      ? "Forecast was too high on average"
                      : "Forecast was too low on average"
                  }
                />
                <Stat
                  label="Worst 10% of misses start at"
                  value={mw(day.metrics.p90_abs_error)}
                  help="90th percentile of absolute error"
                />
                <Stat
                  label="Root mean square error"
                  value={mw(day.metrics.rmse)}
                  help="Penalises large misses more"
                />
              </dl>
            </div>
            <div className="panel">
              <h2>How wrong is it across all of January?</h2>
              <dl className="stats">
                <Stat
                  label="Average miss"
                  value={mw(overall?.overall.mae)}
                  help={`${overall?.overall.n.toLocaleString()} half-hours`}
                />
                <Stat
                  label="Bias"
                  value={mw(overall?.overall.bias)}
                  help="Positive means forecast runs high"
                />
                <Stat
                  label="Worst 10% of misses start at"
                  value={mw(overall?.overall.p90_abs_error)}
                  help="Use this as a buffer size"
                />
                <Stat
                  label="Worst 5% of misses start at"
                  value={mw(overall?.overall.p95_abs_error)}
                  help="95th percentile"
                />
              </dl>
            </div>
          </section>

          <section className="panel">
            <h2>How much to buy from other sources</h2>
            <p className="hint">
              Enter the demand you expect for this day. The tool subtracts the
              forecast wind. Demand data is not part of this pilot, so it is a
              single flat number you provide.
            </p>
            <label className="inline">
              Expected demand (MW)
              <input
                type="number"
                min="0"
                value={demand}
                placeholder="e.g. 30000"
                onChange={(e) => setDemand(e.target.value)}
              />
            </label>
            {hasDemand ? (
              buy <= 0 ? (
                <p className="result">
                  Forecast wind covers all of this demand, with about{" "}
                  <b>{mw(-buy)}</b> to spare on average.
                  {buyWorst > 0 && (
                    <>
                      {" "}
                      If wind falls short by the amount exceeded only 5% of the
                      time, you would need up to <b>{mw(buyWorst)}</b>.
                    </>
                  )}
                </p>
              ) : (
                <p className="result">
                  Average to buy: <b>{mw(buy)}</b>. If wind falls short by the
                  amount exceeded only 5% of the time in January, you would need
                  up to <b>{mw(buyWorst)}</b>.
                </p>
              )
            ) : (
              <p className="result muted">
                Average forecast wind for the day is {mw(meanForecast)}.
              </p>
            )}
          </section>

          <section className="panel">
            <h2>Does an older forecast miss by more?</h2>
            <p className="hint">
              At the deadline, forecasts for late-evening hours are older than
              forecasts for early-morning hours. Each group below is how many
              hours before the target time the forecast was published.
            </p>
            <div className="chart">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={(horizon?.buckets ?? []).map((b) => ({
                    label: `${b.from_h}–${b.to_h}h`,
                    mae: b.mae,
                    bias: b.bias,
                  }))}
                  margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} width={44} />
                  <Tooltip formatter={(v: number) => `${Math.round(v)} MW`} />
                  <Legend />
                  <Bar
                    dataKey="mae"
                    name="Average miss"
                    fill="var(--forecast)"
                  />
                  <Bar
                    dataKey="bias"
                    name="Bias (forecast − actual)"
                    fill="var(--actual)"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="panel">
            <h2>Average miss by hour of day (January)</h2>
            <div className="chart">
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={overall?.by_hour ?? []}
                  margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid stroke="var(--line)" vertical={false} />
                  <XAxis dataKey="hour" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} width={44} />
                  <Tooltip
                    formatter={(v: number) => `${Math.round(v)} MW`}
                    labelFormatter={(h) => `Hour ${h}:00 UTC`}
                  />
                  <Bar
                    dataKey="mae"
                    name="Average miss"
                    fill="var(--forecast)"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <footer className="foot">
            Assumptions: deadline is {String(cutoff).padStart(2, "0")}:00 UTC on
            the day before delivery (UK time equals UTC in January). Hourly
            forecasts are applied to both half-hours of the hour. Error =
            forecast minus actual. Source: Elexon BMRS (WINDFOR, FUELHH).
          </footer>
        </>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  help,
}: {
  label: string;
  value: string;
  help: string;
}) {
  return (
    <div className="stat">
      <dt>{label}</dt>
      <dd>{value}</dd>
      <small>{help}</small>
    </div>
  );
}
