export type Metrics = {
  n: number;
  mae?: number;
  rmse?: number;
  bias?: number;
  mape_pct?: number | null;
  p50_abs_error?: number;
  p90_abs_error?: number;
  p95_abs_error?: number;
  mean_actual?: number;
  err_p05?: number;
  err_p95?: number;
};

export type Point = { t: string; forecast: number; actual: number; published: string };
export type DecisionResponse = { cutoff_hour_utc: number; metrics: Metrics; points: Point[] };
export type HourStat = { hour: number; mae: number; bias: number };
export type MetricsResponse = { cutoff_hour_utc: number; overall: Metrics; by_hour: HourStat[] };
export type HorizonBucket = { from_h: number; to_h: number; n: number; mae: number; bias: number };
export type HorizonResponse = { cutoff_hour_utc: number; buckets: HorizonBucket[] };

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const fetchDecision = (date: string, cutoff: number) =>
  getJson<DecisionResponse>(`/api/v1/decision?date=${date}&cutoff_hour=${cutoff}`);

export const fetchMetrics = (cutoff: number) =>
  getJson<MetricsResponse>(`/api/v1/metrics?cutoff_hour=${cutoff}`);

export const fetchHorizon = (cutoff: number) =>
  getJson<HorizonResponse>(`/api/v1/metrics/by-horizon?cutoff_hour=${cutoff}`);