import pandas as pd
from app.analysis import compute_metrics, join_with_actuals, select_forecast_at_cutoff


def fc(rows):
    return pd.DataFrame(rows, columns=["startTime", "publishTime", "generation"])


def test_picks_latest_before_cutoff_and_ignores_later():
    # Delivery 15 Jan 10:00; cutoff 14 Jan 09:00 (the example from our discussion)
    f = fc([
        ("2026-01-15T10:00Z", "2026-01-13T18:00Z", 3800),
        ("2026-01-15T10:00Z", "2026-01-14T06:00Z", 4100),
        ("2026-01-15T10:00Z", "2026-01-14T12:00Z", 4500),  # after cutoff -> must be ignored
    ])
    out = select_forecast_at_cutoff(f, cutoff_hour=9)
    assert len(out) == 1 and out.iloc[0]["forecast"] == 4100


def test_publish_exactly_at_cutoff_is_allowed():
    f = fc([("2026-01-15T10:00Z", "2026-01-14T09:00Z", 1000)])
    assert len(select_forecast_at_cutoff(f, 9)) == 1


def test_no_forecast_before_cutoff_gives_no_row():
    f = fc([("2026-01-15T10:00Z", "2026-01-14T09:30Z", 1000)])
    assert select_forecast_at_cutoff(f, 9).empty


def test_duplicates_and_unsorted_input():
    f = fc([
        ("2026-01-15T10:00Z", "2026-01-14T08:00Z", 2),
        ("2026-01-15T10:00Z", "2026-01-14T06:00Z", 1),
        ("2026-01-15T10:00Z", "2026-01-14T08:00Z", 2),
    ])
    assert select_forecast_at_cutoff(f, 9).iloc[0]["forecast"] == 2


def test_each_delivery_day_has_its_own_cutoff():
    f = fc([
        ("2026-01-15T10:00Z", "2026-01-14T08:00Z", 10),
        ("2026-01-16T10:00Z", "2026-01-14T08:00Z", 20),
        ("2026-01-16T10:00Z", "2026-01-15T08:00Z", 30),
    ])
    out = select_forecast_at_cutoff(f, 9).set_index(pd.to_datetime(["2026-01-15T10:00Z", "2026-01-16T10:00Z"]))
    assert list(out["forecast"]) == [10, 30]


def test_metrics_and_sign_convention():
    sel = select_forecast_at_cutoff(fc([
        ("2026-01-15T10:00Z", "2026-01-14T06:00Z", 4100),
        ("2026-01-15T10:30Z", "2026-01-14T06:00Z", 3000),
    ]), 9)
    act = pd.DataFrame({"startTime": ["2026-01-15T10:00Z", "2026-01-15T10:30Z"], "generation": [3500, 3400]})
    j = join_with_actuals(sel, act)
    m = compute_metrics(j)
    assert list(j["error"]) == [600, -400]  # + = forecast too high
    assert m["mae"] == 500 and m["bias"] == 100


def test_missing_actual_is_dropped():
    sel = select_forecast_at_cutoff(fc([("2026-01-15T10:00Z", "2026-01-14T06:00Z", 1)]), 9)
    act = pd.DataFrame({"startTime": [], "generation": []})
    assert join_with_actuals(sel, act).empty and compute_metrics(join_with_actuals(sel, act)) == {"n": 0}


def test_upsample_hourly_to_half_hourly():
    from app.analysis import upsample_forecasts_to_half_hourly
    f = fc([("2026-01-15T10:00Z", "2026-01-14T06:00Z", 4100)])
    out = upsample_forecasts_to_half_hourly(f).sort_values("startTime")
    assert [t.strftime("%H:%M") for t in out["startTime"]] == ["10:00", "10:30"]
    assert list(out["generation"]) == [4100, 4100]


def test_forecast_published_after_target_time_is_ignored():
    # Seen in the real data: startTime 4 Jan 21:00, publishTime 5 Jan 22:30
    f = fc([("2026-01-04T21:00Z", "2026-01-05T22:30Z", 11800)])
    assert select_forecast_at_cutoff(f, 9).empty

def test_signed_percentiles_and_horizon_buckets():
    from app.analysis import metrics_by_horizon
    sel = select_forecast_at_cutoff(fc([
        ("2026-01-15T10:00Z", "2026-01-14T06:00Z", 4100),   # horizon 28h
        ("2026-01-15T22:00Z", "2026-01-14T06:00Z", 3000),   # horizon 40h
    ]), 9)
    act = pd.DataFrame({"startTime": ["2026-01-15T10:00Z", "2026-01-15T22:00Z"], "generation": [3500, 3400]})
    j = join_with_actuals(sel, act)
    m = compute_metrics(j)
    assert m["err_p05"] < m["err_p95"]
    b = metrics_by_horizon(j)
    assert [(x["from_h"], x["to_h"], x["n"]) for x in b] == [(24, 30, 1), (36, 48, 1)]