"""Download weekly state initial claims (not seasonally adjusted) from FRED and ALFRED.

data/raw/fred/<SERIES>.csv          the current vintage, full history
data/raw/alfred/<SERIES>/<date>.csv what was published as of each Sunday in the study
                                    period, i.e. what a forecaster knew that day

Rerunnable: files that already exist are not downloaded again.

    python src/fetch_claims.py
"""

import time
from datetime import date, timedelta
from pathlib import Path

import requests

SERIES = ["CAICLAIMS", "WAICLAIMS", "NYICLAIMS", "TXICLAIMS"]
FIRST_SUNDAY = date(2021, 10, 3)
LAST_SUNDAY = date(2026, 11, 1)
LOOKBACK = timedelta(weeks=60)


def get(session, url, params, path):
    if path.exists():
        return
    for attempt in range(6):
        r = session.get(url, params=params, timeout=60)
        if r.ok and r.text.startswith("observation_date"):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text)
            time.sleep(0.3)
            return
        time.sleep(2**attempt)
    raise RuntimeError(f"{url} {params}: {r.status_code} {r.text[:200]}")


def main():
    session = requests.Session()
    for series in SERIES:
        get(session, "https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": series},
            Path(f"data/raw/fred/{series}.csv"))
        sunday = FIRST_SUNDAY
        while sunday <= LAST_SUNDAY:
            get(session, "https://alfred.stlouisfed.org/graph/alfredgraph.csv",
                {"id": series, "vintage_date": sunday.isoformat(),
                 "cosd": (sunday - LOOKBACK).isoformat()},
                Path(f"data/raw/alfred/{series}/{sunday}.csv"))
            sunday += timedelta(weeks=1)
        print(series, "done", flush=True)


if __name__ == "__main__":
    main()
