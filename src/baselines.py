"""The 'how long does this route actually take' baseline.

Two ways to measure it from history (Mon 15th + Tue 16th); we use the
progress-based one as `typical_progress_min`, and keep `typical_naive_min`
only to show why it was rejected (see DECISION_RECORD.md, call #1).

 - naive: first ping in the window to last ping in the window. Inflated by
   the pre-departure / post-arrival dwell that DATA_GUIDE.md says the
   extract is deliberately padded with.
 - progress-based: first ping that leaves the origin stop's catchment, to
   the first ping that reaches the destination stop's catchment.
"""
import pandas as pd
import numpy as np


def historical_runtimes(trips, pings, geo, live_date="2026-06-17"):
    hist = trips[trips.service_date.astype(str).ne(live_date)].copy()

    def estimate(row):
        v, rid = row.vehicle_id, row.route_id
        lo = row.scheduled_start - pd.Timedelta(minutes=15)
        hi = row.scheduled_end + pd.Timedelta(minutes=25)
        sub = pings[(pings.vehicle_id == v) & (pings.recorded_at >= lo) & (pings.recorded_at <= hi)]
        sub = sub.sort_values("recorded_at")
        if sub.empty:
            return pd.Series({"naive_min": np.nan, "progress_min": np.nan, "n_ping": 0})
        prog = sub.apply(lambda r: geo.progress(rid, r.lat, r.lon), axis=1)
        seqs = np.array([x[2] for x in prog])
        naive_min = (sub.recorded_at.iloc[-1] - sub.recorded_at.iloc[0]).total_seconds() / 60
        left_origin = sub[seqs > 1]
        reached_dest = sub[seqs == geo.last_seq[rid]]
        if left_origin.empty or reached_dest.empty:
            progress_min = np.nan
        else:
            progress_min = (
                reached_dest.recorded_at.iloc[0] - left_origin.recorded_at.iloc[0]
            ).total_seconds() / 60
        return pd.Series(
            {"naive_min": round(naive_min, 1), "progress_min": round(progress_min, 1), "n_ping": len(sub)}
        )

    hist = hist.join(hist.apply(estimate, axis=1))
    typical = hist.groupby("route_id")[["naive_min", "progress_min"]].median()
    typical.columns = ["typical_naive_min", "typical_progress_min"]
    return hist, typical
