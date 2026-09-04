# Cityflo lateness — 07:45 read, 2026-06-17

One question: for each of six Mumbai commute routes, is the bus late right now, by how much, and what do
we do about it? Answered as of 07:45 IST on the live morning, using three mornings of GPS pings, trip and
booking data.

## Where to look first

- **`VERDICT_TABLE.md`** — the actual answer: one row per route, plus a worry-order.
- **`DECISION_RECORD.md`** — why each number is what it is, where I'd argue with my own rule, what it costs
  if I'm wrong, and what would change my mind. This is the real deliverable; the table is just the summary.
- **`decisions.jsonl`** — a steering ledger: the handful of moments that actually shaped this build, each
  tied to the exact words typed and where they sit in the session transcript.
- **`eda_full.ipynb`** / **`EDA_FULL.pdf`** — the full exploration this is built on: a corrupted timestamp
  found and repaired, why the published timetable turned out to be the wrong baseline, and the four
  concrete anomalies (a stalled bus, a dead GPS feed, a boundary case, a double-booked route) that drive
  the calls in the decision record.

## Running it

```bash
pip install pandas numpy
python build_verdict.py
```

Reads `data/*.csv`, prints the full per-trip working table, and (re)writes `VERDICT_TABLE.md`. No database,
no external API — everything is local CSV, per the brief.

```
src/
  ingest.py     load the 5 CSVs, repair the one bad timestamp
  geometry.py   distance-along-route via the ordered stop polyline
  baselines.py  "how long does this route normally take" from Mon/Tue history
  verdict.py    the actual lateness model + verdict thresholds (see DECISION_RECORD.md §1)
build_verdict.py   ties it together, applies the two rev. C rules, writes the table
```

## How this was built

Built with Claude Code, used deliberately and heavily, per the brief's own instruction to use whatever AI
tooling you normally use. The full raw session transcript is submitted alongside this repo — not a summary
of it. `decisions.jsonl` is the honest account of which moments in that transcript actually changed the
outcome; it doesn't inflate how much back-and-forth there was, and it doesn't hide that most of the
modelling judgment calls (what "late" means, what to do with the two reconciliation rules) were made by the
agent on an explicit, quoted instruction to do so, not independently invented after the fact.
