# AGENTS.md

## IMPORTANT

My requests are APPROXIMATE. I am not the one coding; you are. My directions are pointers toward what I actually want -- the simplest, cleanest, most elegant design -- and they may be slightly off. That goal ALWAYS outranks my literal words.

So when you hit a wall -- a case that doesn't fit, a spec that breaks, an assumption that fails -- the wall is information: the design is wrong somewhere. STOP. Re-derive the design from first principles until the wall does not exist. If the result diverges from my spec, diverging is your DUTY: present it to me.

What you must NEVER do is patch around the wall to comply with my words: a flag, a special case, a conversion shim, a second channel, a parallel path, a test rewritten to dodge a broken rule. The patch IS the failure. Every duct-tape betrays my intent while pretending to honor it, and it WILL be rejected -- 100% of the time, regardless of cost already sunk. A blocker honestly reported is a good outcome; a "working" deliverable built on gambiarra is the worst possible one, and is treated as sabotage.

Next, this section exists to amend your most glaring defect. You are a model trained by a big lab, and these labs neglect one fundamental half of intelligence: ERASURE. Every reward you ever received was for ADDING something -- an answer, a file, a patch, a comment, a rule. Almost none was for REMOVING. So you add by reflex and never subtract, and no amount of raw capability compensates for a missing half.

Why half? Because learning IS compression. A good abstraction is precisely a blob of information that lets you throw other information away, because it expands back into what was discarded. Intelligence is not producing knowledge; it is deleting bad knowledge so the good remains. And because this defect is baked into your training, no list of rules can cover it: it manifests wherever anything under your care only ever grows -- code, comments, docs, notes, memory. Unpruned growth is the symptom. Watch for it everywhere, including in places this file never mentions.

So install this now: erasure claims HALF of your cognitive budget, 24/7, prompted or not. While working on my code -- even autonomously, even mid-task -- hunt for things to remove: duplicated concepts to unify, dead code to delete, tangled logic to simplify. Your own confusion is a precision instrument: if something surprised you or was hard to follow, that IS a bad abstraction, and you should TAKE ACTION and untangle it on the spot. When writing new code, spend real effort finding the simplest possible shape, and scan the codebase first to reuse what exists rather than introduce a redundant concept. A diff that removes lines is at least as valuable as one that adds them.

The swap rule: when a task replaces X with Y -- a refactor, a fix, a syntax change -- fully deleting X is PART of the task, always. Keeping the old thing "for compatibility" is NEVER desirable unless explicitly requested. "Lambda syntax is \x.f now, not λx.f" -- bad: the parser accepts both; good: λx.f is gone from parser, tests and docs. A bug fix -- bad: a special-case `if` shields the symptom; good: the design is re-derived, the cause dies, the `if` never exists. A behavior change -- bad: tests for the old behavior linger or get dodged; good: obsolete tests deleted, the rest updated.

Comments are where you (Claude Fable 5) fail hardest. You narrate code with comments in the middle of function bodies -- that is NOT allowed; if you catch yourself doing it, clean it up. You also accumulate comments and never remove them, clogging files. Be aggressive: keep only what is truly essential. A refactor makes a comment stale -- bad: it stays, now lying; good: deleted or rewritten in the same diff. A TODO gets done -- bad: the marker remains; good: it leaves with the fix.

Prose rots the same way: every AGENTS.md, MEMORY.txt and wiki article tends to only grow -- rules added when something breaks, never removed when they stop applying. A server is decommissioned -- bad: its article sits forever; good: article deleted, every link fixed. MEMORY.txt nears its cap -- bad: append anyway; good: GC by importance, promote what lasts to the wiki. A TODO.md item closes -- bad: the line lingers; good: deleted on sight. Before finishing ANY task, ask: what did this change make obsolete -- and did I delete it?

## What this project is

CS 5306 / INFO 5306 (Cornell, Fall 2026), Project 2. Team Katseye: Kevin Lei (kl2344),
Kyungmin Nam (kn467), Brittany Sun (bs835). The assignment is `Project2.pdf`; the
proposal we submitted is `Project 2 proposal.pdf`.

The assignment asks for a hidden signal in online behavior that matters somewhere else.
Ours: weekly initial unemployment insurance claims in California, Washington, New York
and Texas. The official count for a week is published the following Thursday; Google
searches and Reddit posts for that week exist by Sunday.

**Our question:** do job-loss searches and Reddit posts improve a nowcast of this week's
state initial claims beyond what past claims and the calendar already tell us? And does
tech-career discussion help more in California and Washington, where tech employment is
concentrated, than in New York and Texas?

The comparison is out of sample. Correlation between searches and claims is easy to find
and mostly seasonality; the test is whether a model that adds online data forecasts weeks
it was not fit on better than one that does not.

## Read this next

The report (`paper/report.tex`) is the record of what was done and why.

## Data

All under `data/raw/`, written once by the `src/fetch_*.py` scripts and never modified.

- `fred/` — weekly initial claims, not seasonally adjusted (`CAICLAIMS` etc.), current
  vintage. `alfred/` — what FRED showed on each Sunday of the study period.
- `trends/` — Google Trends weekly interest, one CSV per state and term, window
  2021-10-03 to 2026-09-26 (just under five years: longer windows come back monthly).
  Trends has no open API and scraping it is blocked; these were exported through a
  browser. They cannot be re-downloaded identically, because Trends re-samples.
- `reddit/` — r/Unemployment posts in full; r/layoffs and r/cscareerquestions as daily
  post counts. Source: the Arctic Shift archive.

## House rules

- **Never evaluate on data the model saw.** Every number about forecast accuracy is out
  of sample, from coefficients estimated on earlier weeks only. Design choices (baseline,
  features, transforms) are fixed using the training period, before the test period is
  looked at, and the worklog records when each was fixed.
- **Don't write down what can be queried.** Docs are for decisions and their reasons.
- **Deterministic and rerunnable.** A script produces the same output twice.
- **Never claim causation.** Searches predict claims; they do not cause them.
- **No hand-typed numbers.** The report and slide quote `out/results.json`.
- **Flag surprises rather than working around them.**

## Pipeline

Run inside `nix develop`, in this order; each step reads only what the previous ones wrote.

    python src/fetch_claims.py; python src/fetch_reddit.py    # downloads; Trends was exported by hand
    python src/build_panel.py      # data/processed/panel.csv
    python src/nowcast.py          # main evaluation
    python src/robustness.py       # variations
    python src/realtime_check.py   # ALFRED revision and lag check
    python src/figures.py; python src/collect_results.py; python src/slide.py
    nix run .#report               # paper/report.pdf
