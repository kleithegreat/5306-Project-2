"""Variations on the main evaluation, one row per (variation, scope, model).

    python src/robustness.py   ->  out/tables/robustness.csv, correlation.csv
"""

import numpy as np
import pandas as pd

from nowcast import BASELINE, HOLIDAY_NAMES, HOLIDAYS, MODELS, TRENDS, accuracy, features, holiday_week, run

TERMS = {"d_trends_file": "file for unemployment", "d_trends_benefits": "unemployment benefits",
         "d_trends_unemployment": "unemployment"}


def stale(f):
    """Features for a nowcast made before week t-1's claims are published.

    The target becomes the two-week change y_t - y_{t-2}; every claims regressor moves
    back a week, and the online regressors cover both unobserved weeks.
    """
    out = []
    for st, d in f.groupby("state"):
        d = d.set_index("week_end").sort_index().copy()
        d["d2y"] = d.dy + d.dy.shift(1)
        d["d2y_lag52"] = d.dy_lag52 + d.dy_lag52.shift(1)
        d["dy_lag2"] = d.dy_lag1.shift(1)
        for h in HOLIDAYS:
            d[f"{h}_prev"] = d[h].shift(1)
        for col in TRENDS + ["d_reddit_state"]:
            d[f"{col}_2w"] = d[col] + d[col].shift(1)
        out.append(d.reset_index())
    return pd.concat(out).dropna(subset=["d2y", "dy_lag2", "d2y_lag52"])


def main():
    panel = pd.read_csv("data/processed/panel.csv", parse_dates=["week_end"])
    f = features(panel)
    rows = []

    def add(variation, fc):
        rows.append(accuracy(fc).assign(variation=variation))

    add("weak baseline (no seasonal or holiday terms)",
        run(f, {"baseline": ["dy_lag1"], "trends": ["dy_lag1"] + TRENDS}))
    add("one Trends term at a time",
        run(f, {"baseline": BASELINE, **{f"trends: {name}": BASELINE + [col] for col, name in TERMS.items()}}))
    stale_base = ["d2y_lag52", "dy_lag2"] + HOLIDAYS + [f"{h}_prev" for h in HOLIDAYS]
    add("claims two weeks stale",
        run(stale(f), {"baseline": stale_base,
                       "trends": stale_base + [f"{c}_2w" for c in TRENDS],
                       "reddit": stale_base + ["d_reddit_state_2w"]}, target="d2y"))
    add("rolling 104-week window", run(f, MODELS, window=104))

    main_fc = pd.read_csv("out/tables/nowcasts.csv", parse_dates=["week_end"])
    for start, end in (("2023-10-01", "2024-09-30"), ("2024-10-01", "2025-09-30"), ("2025-10-01", "2026-09-30")):
        add(f"test year {start[:4]}-{end[2:4]}", main_fc[main_fc.week_end.between(start, end)])

    weeks = pd.DatetimeIndex(main_fc.week_end.unique())
    near = pd.Series(False, index=weeks)
    for name in HOLIDAY_NAMES:
        h = holiday_week(name, weeks.sort_values())
        near |= h | h.shift(1, fill_value=False)
    add("excluding holiday weeks and the week after", main_fc[~main_fc.week_end.map(near)])

    table = pd.concat(rows, ignore_index=True)
    table.to_csv("out/tables/robustness.csv", index=False)
    print(table[table.scope == "pooled"][["variation", "model", "rel_mse", "cw_p"]].round(3).to_string())

    # In-sample correlation over the whole window, in levels and in weekly changes.
    corr = []
    for st, d in f.groupby("state"):
        for col, name in TERMS.items():
            level = np.log1p(panel.set_index(["state", "week_end"]).loc[st, col[2:]]).reindex(d.week_end)
            corr.append({"state": st, "term": name,
                         "corr_levels": np.corrcoef(d.y, level)[0, 1],
                         "corr_changes": d[["dy", col]].dropna().corr().iloc[0, 1]})
    corr = pd.DataFrame(corr)
    corr.to_csv("out/tables/correlation.csv", index=False)
    print(corr.round(2).to_string())


if __name__ == "__main__":
    main()
