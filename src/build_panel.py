"""Build the weekly state panel: claims, Google Trends, and Reddit counts.

One row per (state, week_end), where week_end is the Saturday closing a Sunday-Saturday
week, the convention used by both the claims series and Google Trends. Claims run from
2015 so that year-ago seasonal terms exist; the online columns are null outside the
Trends window.

    python src/build_panel.py   ->  data/processed/panel.csv
"""

import json
import re
from pathlib import Path

import pandas as pd

STATES = {"CA": "California", "WA": "Washington", "NY": "New York", "TX": "Texas"}
TERMS = {"file_for_unemployment": "trends_file", "unemployment_benefits": "trends_benefits",
         "unemployment": "trends_unemployment"}
# Each state's unemployment agency, by the acronym posters use for it.
AGENCIES = {"CA": ["EDD"], "WA": ["ESD"], "NY": ["NYSDOL", "NYDOL"], "TX": ["TWC"]}
CLAIMS_FROM = "2015-01-01"


def week_end(ts):
    """The Saturday that closes the Sunday-Saturday week containing ts."""
    day = ts.dt.normalize()
    return day + pd.to_timedelta((5 - day.dt.weekday) % 7, unit="D")


def claims():
    frames = []
    for st in STATES:
        df = pd.read_csv(f"data/raw/fred/{st}ICLAIMS.csv", parse_dates=["observation_date"])
        df.columns = ["week_end", "claims"]
        frames.append(df.assign(state=st))
    df = pd.concat(frames)
    return df[df.week_end >= CLAIMS_FROM]


def trends():
    frames = []
    for path in sorted(Path("data/raw/trends").glob("*.csv")):
        st, term = path.stem.split("_", 1)
        df = pd.read_csv(path, skiprows=2)
        assert df.columns[1] == f"{term.replace('_', ' ')}: ({STATES[st]})", (path, df.columns)
        value = pd.to_numeric(df.iloc[:, 1].replace("<1", "0.5"))
        week = pd.to_datetime(df.iloc[:, 0]) + pd.Timedelta(days=6)
        frames.append(pd.DataFrame({"state": st, "week_end": week, "series": TERMS[term], "value": value}))
    return pd.concat(frames).pivot_table(index=["state", "week_end"], columns="series", values="value").reset_index()


def tag_state(post):
    """Which of our four states an r/Unemployment post is about, or None.

    The subreddit asks posters to tag their state in brackets, in the flair or the title.
    A post without a tag counts only if its title or body names exactly one of our states
    or its agency.
    """
    for field in (post["link_flair_text"], post["title"]):
        m = re.match(r"\s*[\[(]([^\])]+)[\])]", field)
        if m:
            tag = re.sub(r"[^a-z]", "", m.group(1).lower())
            for st, name in STATES.items():
                if tag in (st.lower(), name.replace(" ", "").lower()):
                    return st
            return None
    text = f"{post['title']} {post['selftext']}"
    hits = {st for st, name in STATES.items()
            if re.search(rf"\b{name}\b", text, re.I)
            or any(re.search(rf"\b{a}\b", text) for a in AGENCIES[st])}
    return hits.pop() if len(hits) == 1 else None


def reddit():
    unemp = pd.DataFrame(json.loads(line) for line in open("data/raw/reddit/Unemployment.jsonl"))
    unemp = unemp.fillna({"title": "", "selftext": "", "link_flair_text": ""})
    unemp["week_end"] = week_end(pd.to_datetime(unemp.created_utc, unit="s"))
    unemp["state"] = [tag_state(p) for p in unemp.to_dict("records")]
    by_state = unemp.dropna(subset=["state"]).groupby(["state", "week_end"]).size().rename("reddit_state")
    national = {"reddit_unemployment": unemp.groupby("week_end").size()}
    for sub, col in (("layoffs", "reddit_layoffs"), ("cscareerquestions", "reddit_cscq")):
        daily = pd.read_csv(f"data/raw/reddit/{sub}_daily.csv", parse_dates=["date"])
        national[col] = daily.groupby(week_end(daily.date)).posts.sum()
    return by_state.reset_index(), pd.DataFrame(national).rename_axis("week_end").reset_index()


def main():
    panel = claims().merge(trends(), on=["state", "week_end"], how="left")
    by_state, national = reddit()
    panel = panel.merge(by_state, on=["state", "week_end"], how="left").merge(national, on="week_end", how="left")
    window = panel.trends_file.notna()
    reddit_cols = ["reddit_state", "reddit_unemployment", "reddit_layoffs", "reddit_cscq"]
    # A week with no posts is a zero, not a missing value, but only inside the window.
    panel[reddit_cols] = panel[reddit_cols].fillna(0).where(window, axis=0)
    panel = panel.sort_values(["state", "week_end"])
    Path("data/processed").mkdir(parents=True, exist_ok=True)
    panel.to_csv("data/processed/panel.csv", index=False, date_format="%Y-%m-%d")
    print(panel[panel.trends_file.notna()].groupby("state")[["claims", "trends_file", "reddit_state", "reddit_cscq"]].describe().T.round(1))


if __name__ == "__main__":
    main()
