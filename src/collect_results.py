"""Every number the report and slide quote, in one file.

    python src/collect_results.py   ->  out/results.json
"""

import json

import pandas as pd

from build_panel import tag_state
from nowcast import FIRST_TEST, FIRST_TRAIN, LAST_WEEK, STATES


def pct(x):
    return round(float(x) * 100, 1)


def model_table(acc):
    out = {}
    for _, r in acc.iterrows():
        out.setdefault(r.scope, {})[r.model] = {
            "rmse_pct": pct(r.rmse), "error_reduction_pct": pct(1 - r.rel_mse),
            **({"cw_p": round(float(r.cw_p), 4)} if r.model != "baseline" else {})}
    return out


def main():
    panel = pd.read_csv("data/processed/panel.csv", parse_dates=["week_end"])
    window = panel[panel.week_end.between(FIRST_TRAIN, LAST_WEEK)]
    acc = pd.read_csv("out/tables/accuracy.csv")
    rob = pd.read_csv("out/tables/robustness.csv")
    corr = pd.read_csv("out/tables/correlation.csv")
    rt = pd.read_csv("out/tables/realtime.csv")

    posts = pd.read_json("data/raw/reddit/Unemployment.jsonl", lines=True)
    posts = posts[pd.to_datetime(posts.created_utc, unit="s").between("2021-10-10", "2026-09-27")]
    posts = posts.fillna({"title": "", "selftext": "", "link_flair_text": ""})
    tagged = pd.Series([tag_state(p) for p in posts.to_dict("records")]).value_counts()
    layoffs = pd.read_csv("data/raw/reddit/layoffs_daily.csv", parse_dates=["date"])

    main_acc = model_table(acc)
    pooled = rob[rob.scope == "pooled"].set_index(["variation", "model"])
    robustness = {v: {m: {"error_reduction_pct": pct(1 - r.rel_mse), "cw_p": round(float(r.cw_p), 4)}
                      for m, r in d.droplevel(0).iterrows() if m != "baseline"}
                  for v, d in pooled.groupby(level=0, sort=False)}
    by_state_terms = rob[rob.variation == "one Trends term at a time"]
    tech = {st: main_acc[st]["tech"] for st in STATES}

    results = {
        "design": {
            "states": STATES,
            "first_training_week": str(FIRST_TRAIN.date()),
            "first_test_week": str(FIRST_TEST.date()),
            "last_test_week": str(LAST_WEEK.date()),
            "test_weeks_per_state": int(acc.n_weeks[acc.scope == STATES[0]].iloc[0]),
            "training_weeks_at_first_test": int(((window.state == STATES[0]) & (window.week_end < FIRST_TEST)).sum()),
        },
        "data": {
            "claims_mean_weekly": window.groupby("state").claims.mean().round(0).astype(int).to_dict(),
            "trends_zero_weeks_pct": {st: pct((window[window.state == st].trends_file == 0).mean()) for st in STATES},
            "reddit_unemployment_posts": int(len(posts)),
            "reddit_posts_tagged": {st: int(tagged.get(st, 0)) for st in STATES},
            "reddit_tagged_per_week": {st: round(tagged.get(st, 0) / window.week_end.nunique(), 1) for st in STATES},
            "reddit_cscq_posts_per_week": int(window.drop_duplicates("week_end").reddit_cscq.mean()),
            "reddit_layoffs_posts_by_year": layoffs.groupby(layoffs.date.dt.year).posts.sum().astype(int)
                                                   .rename(str).to_dict(),
        },
        "realtime": {
            "vintages_checked": int(len(rt)),
            "values_compared": int(rt.values_compared.sum()),
            "values_revised": int(rt.values_revised.sum()),
            "sundays_latest_week_unpublished_pct": pct((rt.weeks_behind > 1).mean()),
        },
        "main": main_acc,
        "tech": tech,
        "single_terms": {st: {m.replace("trends: ", ""): pct(1 - r.rel_mse)
                              for m, r in d.set_index("model").iterrows() if m != "baseline"}
                         for st, d in by_state_terms.groupby("scope")},
        "robustness_pooled": robustness,
        "correlation": {st: d.set_index("term")[["corr_levels", "corr_changes"]].round(2).to_dict("index")
                        for st, d in corr.groupby("state")},
    }
    results["where_gain"] = where_gain(pd.read_csv("out/tables/nowcasts.csv", parse_dates=["week_end"]))
    with open("out/results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results["where_gain"], indent=2))


EVENTS = {"hurricane_beryl": ("TX", "2024-07-13"), "los_angeles_fires": ("CA", "2025-01-11")}


def where_gain(fc):
    """How concentrated the Trends gain is, and the two disaster weeks in detail.

    Errors are in log points times 100, roughly percent of the week's claims.
    """
    wide = fc.pivot_table(index=["state", "week_end"], columns="model", values="pred")
    actual = fc.drop_duplicates(["state", "week_end"]).set_index(["state", "week_end"]).actual
    e_base, e_tr = actual - wide.baseline, actual - wide.trends
    gain = e_base**2 - e_tr**2
    out = {}
    for st in STATES:
        g = gain.loc[st].sort_values(ascending=False)
        out[st] = {"top10_weeks_share_of_gain_pct": pct(g.head(10).sum() / g.sum()) if g.sum() > 0 else None,
                   "weeks_trends_closer_pct": pct((g > 0).mean()),
                   "top_weeks": [str(w.date()) for w in g.head(5).index]}
    out["pooled_weeks_trends_closer_pct"] = pct((gain > 0).mean())
    for name, (st, week) in EVENTS.items():
        key = (st, pd.Timestamp(week))
        out[name] = {"state": st, "week_end": week, "actual_change_pct": pct(actual[key]),
                     "baseline_error_pct": pct(e_base[key]), "trends_error_pct": pct(e_tr[key]),
                     "share_of_state_gain_pct": pct(gain[key] / gain.loc[st].sum())}
    return out


if __name__ == "__main__":
    main()
