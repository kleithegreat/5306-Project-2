"""How different is what FRED showed on each Sunday from what it shows now?

For every Sunday vintage in data/raw/alfred/ and every week it contains, compares the
value then with the current value, and records how far behind the newest week was.

    python src/realtime_check.py   ->  out/tables/realtime.csv
"""

from pathlib import Path

import pandas as pd

STATES = ["CA", "WA", "NY", "TX"]


def main():
    rows = []
    for st in STATES:
        current = pd.read_csv(f"data/raw/fred/{st}ICLAIMS.csv", parse_dates=["observation_date"])
        current = current.set_index("observation_date").iloc[:, 0]
        for path in sorted(Path(f"data/raw/alfred/{st}ICLAIMS").glob("*.csv")):
            sunday = pd.Timestamp(path.stem)
            if sunday > pd.Timestamp("2026-09-27"):
                continue
            then = pd.read_csv(path, parse_dates=["observation_date"]).set_index("observation_date").iloc[:, 0]
            lag = (sunday - pd.Timedelta(days=1) - then.index.max()).days // 7
            revised = (then != current.reindex(then.index)).sum()
            rows.append({"state": st, "sunday": sunday.date(), "weeks_behind": lag,
                         "values_compared": len(then), "values_revised": revised,
                         "max_abs_revision_pct": (then / current.reindex(then.index) - 1).abs().max() * 100})
    df = pd.DataFrame(rows)
    df.to_csv("out/tables/realtime.csv", index=False)
    print(df.groupby("state").agg(sundays=("sunday", "size"), latest_week_missing=("weeks_behind", lambda x: (x > 1).mean()),
                                  revised=("values_revised", "sum"), compared=("values_compared", "sum")))


if __name__ == "__main__":
    main()
