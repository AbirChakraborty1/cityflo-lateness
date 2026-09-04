"""Top-level entry point: loads data, builds the 07:45 verdict table.

Run with:  python build_verdict.py

Produces (in the project root):
  - prints the full per-trip working table (for audit)
  - VERDICT_TABLE.md  -- the one-row-per-route table Priya reads at 07:45
"""
import sys
import pandas as pd

sys.path.insert(0, "src")
from ingest import load
from geometry import RouteGeometry
from baselines import historical_runtimes
from verdict import build_verdicts

AS_OF = pd.Timestamp("2026-06-17 07:45:00+05:30")
LIVE_DATE = "2026-06-17"
DROP_OPERATOR_ID = 7  # rev. C rule 1


def main():
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 40)

    data = load("data")
    routes, stops, trips, bookings, pings = (
        data["routes"], data["stops"], data["trips"], data["bookings"], data["pings"]
    )
    geo = RouteGeometry(stops)
    _, typical = historical_runtimes(trips, pings, geo, live_date=LIVE_DATE)

    t17 = trips[trips.service_date.astype(str).eq(LIVE_DATE)].copy()
    from verdict import live_snapshot
    snapshot = live_snapshot(t17, pings, geo, AS_OF)

    per_trip = build_verdicts(t17, snapshot, bookings, typical, geo, AS_OF)
    per_trip = per_trip.merge(routes[["route_id", "route_name"]], on="route_id", how="left")

    print("=== Per-trip working table (before applying rule 1's output filter) ===")
    print(per_trip[["trip_id", "route_id", "route_name", "operator_id", "progress_pct",
                    "verdict", "minutes", "reason"]].to_string(index=False))

    # --- rule 1: operator 7 vehicles are excluded from the OUTPUT table ---
    # (see DECISION_RECORD.md call #2 -- we comply for the rider-facing table,
    #  but we do NOT let it become a blind spot: it's still printed above.)
    output_trips = per_trip[per_trip.operator_id != DROP_OPERATOR_ID].copy()
    dropped = per_trip[per_trip.operator_id == DROP_OPERATOR_ID]

    # route 21 has two trips; after dropping operator 7 (TRIP_019), only
    # TRIP_018 remains, so "one row per route" resolves on its own here.
    assert output_trips.route_id.duplicated().sum() == 0, "route still has >1 trip after the operator-7 drop"

    # --- rule 2: Route 12 is NOT forced to lateness=0. See DECISION_RECORD.md
    #     call #3 for why -- the real number stands in the rider-facing table.

    verdict_table = output_trips.sort_values("route_id")[
        ["route_id", "route_name", "verdict", "minutes", "reason"]
    ].reset_index(drop=True)

    # worry order: PUSH_LATE/CALL_DRIVER ranked by how bad + how confident,
    # NO_VERDICT ranked above HOLD (an unknown is a bigger operational risk
    # than a bus running fine), HOLD last.
    rank_key = {"CALL_DRIVER": 0, "PUSH_LATE": 1, "NO_VERDICT": 2, "HOLD": 3}
    ranked = verdict_table.assign(
        _rank=verdict_table.verdict.map(rank_key),
        _severity=-verdict_table.minutes.fillna(0).abs(),
    )
    worry_order = ranked.sort_values(["_rank", "_severity"]).drop(columns=["_rank", "_severity"])

    print("\n=== Dropped from output by rule 1 (operator 7) ===")
    print(dropped[["trip_id", "route_id", "route_name", "verdict", "minutes", "reason"]].to_string(index=False)
         if len(dropped) else "(none)")

    print("\n=== VERDICT TABLE (07:45, 2026-06-17) ===")
    print(verdict_table.to_string(index=False))

    # write VERDICT_TABLE.md
    lines = [
        "# Verdict table — 07:45 IST, 2026-06-17",
        "",
        "| route | verdict | note |",
        "|---|---|---|",
    ]
    for _, r in worry_order.iterrows():
        v = r.verdict if r.verdict != "PUSH_LATE" else f"PUSH_LATE {abs(r.minutes):.0f} min"
        lines.append(f"| {r.route_name} (route {r.route_id}) | {v} | {r.reason} |")
    lines += [
        "",
        "## Worry order (chase in this order if you can only do one)",
        "",
    ]
    for i, (_, r) in enumerate(worry_order.iterrows(), 1):
        lines.append(f"{i}. **Route {r.route_id} ({r.route_name})** — {r.verdict}"
                    + (f", {abs(r.minutes):.0f} min" if r.verdict == "PUSH_LATE" else "")
                    + f" — {r.reason}")
    lines += [
        "",
        f"## Excluded from this table (rev. C rule 1 — operator {DROP_OPERATOR_ID} vehicles)",
        "",
    ]
    if len(dropped):
        for _, r in dropped.iterrows():
            lines.append(f"- **{r.trip_id}**, route {r.route_id} ({r.route_name}): internally reads "
                        f"**{r.verdict}{f' {abs(r.minutes):.0f} min' if r.verdict == 'PUSH_LATE' else ''}** "
                        f"({r.reason}) — excluded from the rider-facing table per the onboarding SOP, "
                        "not because the data says it's fine. See DECISION_RECORD.md call #2.")
    else:
        lines.append("(none this morning)")

    with open("VERDICT_TABLE.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\nwrote VERDICT_TABLE.md")


if __name__ == "__main__":
    main()
