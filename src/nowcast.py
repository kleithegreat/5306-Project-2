"""Out-of-sample nowcasts of weekly state initial claims, with and without online signals.

Every model predicts the week-over-week log change in claims, dy_t = log c_t - log c_{t-1},
from information available on the Sunday after week t ends: claims through week t-1 and
online activity through week t. Coefficients are re-estimated every week on all earlier
weeks (expanding window), so no forecast uses a coefficient fit on its own outcome.

    python src/nowcast.py   ->  out/tables/nowcasts.csv, accuracy.csv, accuracy.md
"""

from pathlib import Path

import numpy as np
import pandas as pd
from dateutil.easter import easter
from scipy import stats

FIRST_TRAIN = pd.Timestamp("2021-10-16")
FIRST_TEST = pd.Timestamp("2023-10-07")
LAST_WEEK = pd.Timestamp("2026-09-26")
STATES = ["CA", "WA", "NY", "TX"]
TRENDS = ["d_trends_file", "d_trends_benefits", "d_trends_unemployment"]


def holiday(name, year):
    if name == "thanksgiving":
        nov1 = pd.Timestamp(year, 11, 1)
        return nov1 + pd.Timedelta(days=(3 - nov1.weekday()) % 7 + 21)
    if name == "easter":
        return pd.Timestamp(easter(year))
    return {"christmas": pd.Timestamp(year, 12, 25), "newyear": pd.Timestamp(year, 1, 1)}[name]


HOLIDAY_NAMES = ("thanksgiving", "christmas", "newyear", "easter")


def holiday_week(name, weeks):
    """Whether each Sunday-Saturday week (indexed by its Saturday) contains the holiday."""
    days = [holiday(name, y) for y in range(weeks.min().year - 2, weeks.max().year + 2)]
    return pd.Series([any(w - pd.Timedelta(days=6) <= d <= w for d in days) for w in weeks], index=weeks)


def holiday_terms(weeks):
    """Calendar regressors for holidays that move relative to the 52-week lag.

    The seasonal term dy_{t-52} carries last year's holiday effect into this year's week.
    When a holiday falls in week t this year but not in week t-52 (or the reverse), that
    term is misaligned; these contrasts let the model correct it, for the holiday week
    and for the rebound the week after.
    """
    out = {}
    for name in HOLIDAY_NAMES:
        in_week = holiday_week(name, weeks).astype(float)
        out[f"hol_{name}"] = in_week - in_week.shift(52)
        out[f"hol_{name}_next"] = in_week.shift(1) - in_week.shift(53)
    return pd.DataFrame(out)


HOLIDAYS = list(holiday_terms(pd.date_range("2020-01-04", periods=120, freq="W-SAT")).columns)
BASELINE = ["dy_lag52", "dy_lag1"] + HOLIDAYS
MODELS = {
    "baseline": BASELINE,
    "trends": BASELINE + TRENDS,
    "reddit": BASELINE + ["d_reddit_state"],
    "trends+reddit": BASELINE + TRENDS + ["d_reddit_state"],
    "tech": BASELINE + ["d_reddit_cscq"],
}


def features(panel):
    """One row per (state, week_end) with the target and every candidate regressor."""
    frames = []
    for st, d in panel.groupby("state"):
        d = d.set_index("week_end").sort_index()
        y = np.log(d.claims)
        f = pd.DataFrame({"y": y, "dy": y.diff()})
        f["dy_lag1"] = f.dy.shift(1)
        f["dy_lag52"] = f.dy.shift(52)
        f = f.join(holiday_terms(d.index))
        for col in ("trends_file", "trends_benefits", "trends_unemployment", "reddit_state", "reddit_cscq"):
            f[f"d_{col}"] = np.log1p(d[col]).diff()
        frames.append(f.assign(state=st))
    f = pd.concat(frames).reset_index()
    return f[(f.week_end >= FIRST_TRAIN) & (f.week_end <= LAST_WEEK)]


def nowcast(f, cols, target="dy", first_test=FIRST_TEST, window=None):
    """Expanding-window OLS forecasts for every test week of one state's rows."""
    f = f.sort_values("week_end")
    X = np.column_stack([np.ones(len(f)), f[cols].to_numpy(dtype=float)])
    y = f[target].to_numpy(dtype=float)
    assert not np.isnan(X).any() and not np.isnan(y).any(), "missing regressor or target"
    weeks = f.week_end.to_numpy()
    preds = {}
    for i in np.flatnonzero(weeks >= np.datetime64(first_test)):
        lo = max(0, i - window) if window else 0
        beta = np.linalg.lstsq(X[lo:i], y[lo:i], rcond=None)[0]
        preds[weeks[i]] = X[i] @ beta
    return pd.Series(preds, name="pred")


def run(f, models, **kw):
    """Long table of forecasts: state, week_end, model, actual, pred."""
    rows = []
    for st, d in f.groupby("state"):
        for name, cols in models.items():
            p = nowcast(d, cols, **kw)
            target = kw.get("target", "dy")
            rows.append(pd.DataFrame({"state": st, "week_end": p.index, "model": name,
                                      "actual": d.set_index("week_end").loc[p.index, target].to_numpy(),
                                      "pred": p.to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def clark_west(adj, lags=4):
    """One-sided Clark-West (2007) test that the larger nested model forecasts better.

    adj is the adjusted loss differential e_base^2 - (e_alt^2 - (f_base - f_alt)^2).
    Plain Diebold-Mariano is undersized for nested models: under the null, the larger
    model's extra coefficients add estimation noise that makes it look worse than it is.
    Newey-West variance with `lags` lags; returns (t, p).
    """
    n = len(adj)
    c = adj - adj.mean()
    lrv = c @ c / n + sum(2 * (1 - k / (lags + 1)) * (c[k:] @ c[:-k]) / n for k in range(1, lags + 1))
    t = adj.mean() / np.sqrt(lrv / n)
    return t, 1 - stats.norm.cdf(t)


def accuracy(fc, groups=("state",)):
    """RMSE of each model and its comparison with the baseline, per group and pooled."""
    wide = fc.pivot_table(index=["state", "week_end"], columns="model", values="pred")
    actual = fc.drop_duplicates(["state", "week_end"]).set_index(["state", "week_end"]).actual
    rows = []
    scopes = [(st, wide.loc[[st]], actual.loc[[st]]) for st in wide.index.unique("state")]
    scopes.append(("pooled", wide, actual))
    for scope, w, a in scopes:
        base = w["baseline"]
        rmse_base = np.sqrt(np.mean((a - base) ** 2))
        for model in w.columns:
            rmse = np.sqrt(np.mean((a - w[model]) ** 2))
            row = {"scope": scope, "model": model, "n_weeks": len(a), "rmse": rmse,
                   "mae": np.mean(np.abs(a - w[model])), "rel_mse": (rmse / rmse_base) ** 2}
            if model != "baseline":
                # Pooled: average the four states' adjusted differentials within each
                # week, so the HAC correction runs over one time series, not a stack.
                adj = (a - base) ** 2 - ((a - w[model]) ** 2 - (base - w[model]) ** 2)
                if scope == "pooled":
                    adj = adj.groupby(level="week_end").mean()
                row["cw_t"], row["cw_p"] = clark_west(adj.to_numpy())
            rows.append(row)
    return pd.DataFrame(rows)


def main():
    panel = pd.read_csv("data/processed/panel.csv", parse_dates=["week_end"])
    f = features(panel)
    fc = run(f, MODELS)
    acc = accuracy(fc)
    out = Path("out/tables")
    out.mkdir(parents=True, exist_ok=True)
    fc.to_csv(out / "nowcasts.csv", index=False, date_format="%Y-%m-%d")
    acc.to_csv(out / "accuracy.csv", index=False)
    print(acc.pivot(index="model", columns="scope", values="rel_mse").round(3))
    print(acc.pivot(index="model", columns="scope", values="cw_p").round(3))


if __name__ == "__main__":
    main()
