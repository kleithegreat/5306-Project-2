"""Figures for the report, drawn from out/tables/ and the panel; nothing is re-estimated.

    python src/figures.py   ->  out/figures/fig*.pdf
"""

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path("out/figures")
STATES = ["CA", "WA", "NY", "TX"]
NAMES = {"CA": "California", "WA": "Washington", "NY": "New York", "TX": "Texas"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
COLOR = {"baseline": "#8a8984", "trends": "#2a78d6", "reddit": "#eb6834", "tech": "#1baf7a",
         "trends+reddit": "#6250d6", "actual": INK}
LABEL = {"trends": "+ Google Trends", "reddit": "+ r/Unemployment (state)",
         "trends+reddit": "+ both", "tech": "+ r/cscareerquestions"}

plt.rcParams.update({
    "font.family": "serif", "font.size": 8, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
    "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
    "legend.frameon": False, "pdf.fonttype": 42,
})


def zscore(s):
    return (s - s.mean()) / s.std()


def fig1_series(panel):
    """Claims and searches move together, mostly through the seasonal cycle."""
    fig, axes = plt.subplots(4, 1, figsize=(7, 6.2), sharex=True)
    for ax, st in zip(axes, STATES):
        d = panel[(panel.state == st) & panel.trends_file.notna()]
        ax.plot(d.week_end, zscore(np.log(d.claims)), color=INK, lw=1.0, label="initial claims (log)")
        ax.plot(d.week_end, zscore(np.log1p(d.trends_unemployment)), color=COLOR["trends"], lw=1.0,
                label='Google searches for "unemployment" (log)')
        ax.axvline(pd.Timestamp("2023-10-01"), color=MUTED, lw=0.8, ls="--")
        ax.set_ylabel(NAMES[st])
        ax.set_yticks([-2, 0, 2])
    axes[0].text(pd.Timestamp("2023-10-15"), 3.2, "test period begins", color=MUTED, fontsize=7, va="top")
    axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=2)
    fig.supylabel("standard deviations from the state's mean", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig1_series.pdf", bbox_inches="tight")


def fig2_accuracy(acc):
    """Out-of-sample MSE of each augmented model relative to the baseline."""
    models = ["trends", "reddit", "tech"]
    scopes = STATES + ["pooled"]
    fig, ax = plt.subplots(figsize=(3.4, 2.9))
    for j, m in enumerate(models):
        a = acc[acc.model == m].set_index("scope").loc[scopes]
        x = np.arange(len(scopes)) + (j - 1) * 0.22
        ax.scatter(x, (1 - a.rel_mse) * 100, s=22, color=COLOR[m], label=LABEL[m], zorder=3,
                   edgecolor="white", linewidth=0.8)
        for xi, (_, r) in zip(x, a.iterrows()):
            if r.cw_p < 0.05:
                ax.text(xi, (1 - r.rel_mse) * 100 + 1.2, "*", ha="center", color=INK, fontsize=9)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(range(len(scopes)), [NAMES.get(s, "Pooled") for s in scopes], fontsize=6.5)
    ax.set_ylabel("error reduction vs. baseline (% of MSE)")
    ax.set_ylim(top=28)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=6.5)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_accuracy.pdf", bbox_inches="tight")


STATE_COLOR = {"CA": "#2a78d6", "WA": "#eb6834", "NY": "#1baf7a", "TX": "#6250d6"}
EVENTS = [("TX", "2024-07-13", "Hurricane Beryl", (-48, 8)), ("CA", "2025-01-11", "Los Angeles fires", (-15, 28))]


def fig3_where(fc, panel):
    """Where the Trends gain comes from: cumulative gain over the test period, and one event."""
    wide = fc.pivot_table(index=["state", "week_end"], columns="model", values="pred")
    actual = fc.drop_duplicates(["state", "week_end"]).set_index(["state", "week_end"]).actual
    gain = (actual - wide.baseline) ** 2 - (actual - wide.trends) ** 2
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(7, 2.5), gridspec_kw={"width_ratios": [1.6, 1]})
    for st in STATES:
        g = gain.loc[st].cumsum()
        ax.plot(g.index, g, color=STATE_COLOR[st], lw=1.2, label=NAMES[st])
    for st, week, name, offset in EVENTS:
        y = gain.loc[st].cumsum().loc[pd.Timestamp(week)]
        ax.annotate(name, (pd.Timestamp(week), y), xytext=offset, textcoords="offset points",
                    fontsize=6.5, color=MUTED, ha="center", arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.6})
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylabel("cumulative reduction in squared error")
    ax.legend(loc="upper left", fontsize=6.5)
    ax.set_title("(a) Gain from Google Trends over the test period", fontsize=8, loc="left")
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.tick_params(axis="x", labelsize=6.5)

    st, start, end = "TX", "2024-06-01", "2024-08-31"
    claims = panel[panel.state == st].set_index("week_end").claims
    d = fc[(fc.state == st) & fc.week_end.between(start, end)]
    weeks = d.week_end.unique()
    bx.plot(weeks, claims.loc[weeks] / 1000, color=INK, lw=1.4, marker="o", ms=2.5, label="published")
    for m, label in (("baseline", "baseline nowcast"), ("trends", "+ Google Trends")):
        dm = d[d.model == m].set_index("week_end")
        level = claims.shift(1).loc[dm.index] * np.exp(dm.pred)
        bx.plot(level.index, level / 1000, color=COLOR[m], lw=1.0, ls="--" if m == "baseline" else "-", label=label)
    bx.set_ylabel("Texas initial claims (thousands)")
    bx.xaxis.set_major_locator(mdates.MonthLocator())
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    bx.tick_params(axis="x", labelsize=6.5)
    bx.legend(loc="upper left", fontsize=6.5)
    bx.set_title("(b) Texas around Hurricane Beryl, 2024", fontsize=8, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig3_where.pdf", bbox_inches="tight")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv("data/processed/panel.csv", parse_dates=["week_end"])
    fc = pd.read_csv("out/tables/nowcasts.csv", parse_dates=["week_end"])
    acc = pd.read_csv("out/tables/accuracy.csv")
    fig1_series(panel)
    fig2_accuracy(acc)
    fig3_where(fc, panel)


if __name__ == "__main__":
    main()
