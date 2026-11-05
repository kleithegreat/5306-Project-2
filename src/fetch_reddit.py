"""Download the study subreddits from the Arctic Shift archive.

r/Unemployment is downloaded post by post, because assigning a post to a state needs its
title, flair, and text. The tech subreddits only enter as weekly volume, so for them the
archive's daily post counts are enough; counting the full post download for one week of
r/cscareerquestions reproduced those counts exactly (docs/worklog.md).

    data/raw/reddit/Unemployment.jsonl     one post per line
    data/raw/reddit/<subreddit>_daily.csv  date, posts

Rerunnable: the post download resumes from its last timestamp; count files are rewritten.

    python src/fetch_reddit.py [subreddit ...]
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

API = "https://arctic-shift.photon-reddit.com/api/posts/search"
START = datetime(2021, 9, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 1, tzinfo=timezone.utc)
POSTS = {"Unemployment": "id,created_utc,title,link_flair_text,selftext"}
COUNTS = ["layoffs", "cscareerquestions"]
OUT = Path("data/raw/reddit")


def get(session, url, params):
    for attempt in range(8):
        r = session.get(url, params=params, timeout=120)
        if r.ok and r.json().get("data") is not None:
            time.sleep(0.5)
            return r.json()["data"]
        time.sleep(2**attempt)
    raise RuntimeError(f"{url} {params}: {r.status_code} {r.text[:200]}")


def fetch_posts(session, subreddit, fields):
    path = OUT / f"{subreddit}.jsonl"
    seen, after = set(), int(START.timestamp())
    if path.exists():
        for line in path.open():
            post = json.loads(line)
            seen.add(post["id"])
            after = max(after, post["created_utc"])
    with path.open("a") as f:
        while True:
            # `after` is exclusive, so step back one second to keep posts sharing the
            # boundary timestamp; the id set drops the repeats.
            page = get(session, API, {"subreddit": subreddit, "after": after - 1,
                                      "before": int(END.timestamp()), "sort": "asc",
                                      "limit": 100, "fields": fields})
            new = [p for p in page if p["id"] not in seen]
            if not new:
                break
            for post in new:
                seen.add(post["id"])
                f.write(json.dumps(post) + "\n")
            after = max(p["created_utc"] for p in new)
            print(subreddit, datetime.fromtimestamp(after, timezone.utc).date(), len(seen), flush=True)


def fetch_counts(session, subreddit):
    """Daily counts, one month per request, appended so an interrupted run resumes."""
    path = OUT / f"{subreddit}_daily.csv"
    done = set(pd.read_csv(path, parse_dates=["date"]).date.dt.to_period("M")) if path.exists() else set()
    for month in pd.date_range(START.date(), END.date(), freq="MS", inclusive="left"):
        if month.to_period("M") in done:
            continue
        data = get(session, f"{API}/aggregate", {
            "subreddit": subreddit, "aggregate": "created_utc", "frequency": "day",
            "after": month.date().isoformat(), "before": (month + pd.offsets.MonthBegin()).date().isoformat()})
        rows = pd.DataFrame([(pd.Timestamp(d["created_utc"]).tz_convert("UTC").ceil("D").date(), int(d["count"]))
                             for d in data], columns=["date", "posts"])
        rows.to_csv(path, mode="a", header=not path.exists(), index=False)
        print(subreddit, month.date(), flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    for subreddit in sys.argv[1:] or [*POSTS, *COUNTS]:
        if subreddit in POSTS:
            fetch_posts(session, subreddit, POSTS[subreddit])
        else:
            fetch_counts(session, subreddit)


if __name__ == "__main__":
    main()
