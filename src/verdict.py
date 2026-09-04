"""Turns the live-morning snapshot into the 07:45 verdict table.

The definition of "late" used here (see DECISION_RECORD.md call #1):

  PRIMARY  -- promise-breach: for the next boarding stop the bus hasn't
             reached yet, project its arrival (using the route's typical
             pace, not raw instantaneous speed, which is too noisy at low
             speed) and compare against the earliest promised_eta at that
             stop. This is "how late is the bus against what we told the
             rider," which is the number that actually determines whether
             a push is honest.

  CROSS-CHECK -- typical-progress: elapsed time vs. how far the bus should
             be if it were running at this route's typical (historical,
             progress-based) pace. Used to sanity-check the primary number
             and to catch cases where the two disagree.

Thresholds (stated so they're re-runnable, not vibes):
  - last ping older than 300s  -> NO_VERDICT (telemetry not trustworthy)
  - progress <= 2% of route AND >= 15 min since scheduled departure
        -> CALL_DRIVER (not "running late" -- may not have left)
  - trip already at/near 100% progress -> HOLD, informational note only
  - trip not yet at scheduled_start -> HOLD, not due yet
  - |promise-breach| < 5 min -> HOLD
  - promise-breach >= 5 min AND cross-check agrees in direction -> PUSH_LATE
  - promise-breach and cross-check disagree by more than 15 min -> NO_VERDICT
"""
import pandas as pd
import numpy as np

STALE_S = 300
NOT_MOVED_PROGRESS_PCT = 0.02
NOT_MOVED_MIN_ELAPSED_MIN = 15
HOLD_BAND_MIN = 5
DISAGREEMENT_MIN = 15


def live_snapshot(t17, pings, geo, as_of, lookback_min=15):
    rows = []
    for _, row in t17.iterrows():
        v, rid = row.vehicle_id, row.route_id
        lo = row.scheduled_start - pd.Timedelta(minutes=lookback_min)
        sub = pings[(pings.vehicle_id == v) & (pings.recorded_at >= lo) & (pings.recorded_at <= as_of)]
        sub = sub.sort_values("recorded_at")
        total = geo.route_len[rid]
        if sub.empty:
            rows.append(dict(trip_id=row.trip_id, route_id=rid, vehicle_id=v, operator_id=row.operator_id,
                             last_ping=pd.NaT, age_s=None, speed=None, progress_km=0.0, progress_pct=0.0,
                             drift_km=None, has_started=False))
            continue
        last = sub.iloc[-1]
        prog_km, drift_km, _ = geo.progress(rid, last.lat, last.lon)
        rows.append(dict(trip_id=row.trip_id, route_id=rid, vehicle_id=v, operator_id=row.operator_id,
                         last_ping=last.recorded_at, age_s=(as_of - last.recorded_at).total_seconds(),
                         speed=last.speed_kmph, progress_km=prog_km,
                         progress_pct=min(prog_km / total, 1.0), drift_km=drift_km, has_started=True))
    return pd.DataFrame(rows)


def promise_breach(route_id, trip_id, progress_km, last_ping, pace_km_per_min, bookings, geo):
    bk = bookings[bookings.trip_id == trip_id].copy()
    if bk.empty or pace_km_per_min is None or pace_km_per_min <= 0:
        return None
    bk["boarding_dist_km"] = bk.boarding_stop_id.map(geo.stop_dist_km)
    ahead = bk[bk.boarding_dist_km > progress_km + 1e-9]
    if ahead.empty:
        return None
    next_dist = ahead.boarding_dist_km.min()
    at_next_stop = ahead[np.isclose(ahead.boarding_dist_km, next_dist)]
    time_to_reach_min = (next_dist - progress_km) / pace_km_per_min
    est_arrival = last_ping + pd.Timedelta(minutes=time_to_reach_min)
    worst_promise = at_next_stop.promised_eta.min()
    breach_min = (est_arrival - worst_promise).total_seconds() / 60
    return dict(breach_min=breach_min, est_arrival=est_arrival, promised_eta=worst_promise,
               next_stop_dist_km=next_dist, n_bookings_at_stop=len(at_next_stop))


def build_verdicts(t17, snapshot, bookings, typical, geo, as_of):
    typical_progress = typical["typical_progress_min"].to_dict()
    out = []
    for _, row in t17.iterrows():
        rid, trip_id = row.route_id, row.trip_id
        snap = snapshot[snapshot.trip_id == trip_id].iloc[0]
        total_km = geo.route_len[rid]
        typ_min = typical_progress.get(rid)
        pace = (total_km / typ_min) if typ_min else None

        rec = dict(trip_id=trip_id, route_id=rid, vehicle_id=row.vehicle_id, operator_id=row.operator_id,
                  progress_pct=round(snap.progress_pct * 100, 1), age_s=snap.age_s)

        # not started yet
        if not snap.has_started:
            rec.update(verdict="HOLD", minutes=None, reason="not yet due to depart")
            out.append(rec)
            continue

        # stale telemetry
        if snap.age_s is not None and snap.age_s > STALE_S:
            rec.update(verdict="NO_VERDICT", minutes=None,
                      reason=f"last position is {snap.age_s/60:.0f} min old -- can't trust a number this stale")
            out.append(rec)
            continue

        # hasn't moved since departure
        elapsed_min = (snap.last_ping - row.scheduled_start).total_seconds() / 60
        if snap.progress_pct <= NOT_MOVED_PROGRESS_PCT and elapsed_min >= NOT_MOVED_MIN_ELAPSED_MIN:
            rec.update(verdict="CALL_DRIVER", minutes=round(elapsed_min, 1),
                      reason=f"GPS shows no movement from the origin stop for {elapsed_min:.0f} min -- "
                              "not congestion, may not have left")
            out.append(rec)
            continue

        # already complete
        if snap.progress_pct >= 0.999:
            cross_check = elapsed_min - snap.progress_pct * typ_min if typ_min else None
            rec.update(verdict="HOLD", minutes=round(cross_check, 1) if cross_check is not None else None,
                      reason="trip already complete -- informational only, nothing to push now")
            out.append(rec)
            continue

        # primary: promise breach
        pb = promise_breach(rid, trip_id, snap.progress_km, snap.last_ping, pace, bookings, geo)
        cross_check = (elapsed_min - snap.progress_pct * typ_min) if typ_min else None

        if pb is None:
            # no upcoming promise to check -- fall back to cross-check alone
            if cross_check is None:
                rec.update(verdict="NO_VERDICT", minutes=None, reason="no promise data and no historical baseline")
            elif abs(cross_check) < HOLD_BAND_MIN:
                rec.update(verdict="HOLD", minutes=round(cross_check, 1), reason="running close to its typical pace")
            else:
                rec.update(verdict="PUSH_LATE" if cross_check > 0 else "HOLD",
                          minutes=round(cross_check, 1),
                          reason="no upcoming rider promise left to check; based on typical-pace cross-check only")
            out.append(rec)
            continue

        breach = pb["breach_min"]
        agree = cross_check is not None and (
            (breach >= 0) == (cross_check >= 0) or abs(cross_check) < HOLD_BAND_MIN
        )
        disagreement = abs(breach - cross_check) if cross_check is not None else 0

        if disagreement > DISAGREEMENT_MIN:
            rec.update(verdict="NO_VERDICT", minutes=round(breach, 1),
                      reason=f"promise-breach ({breach:+.0f} min) and typical-pace cross-check "
                              f"({cross_check:+.0f} min) disagree by {disagreement:.0f} min")
        elif abs(breach) < HOLD_BAND_MIN:
            rec.update(verdict="HOLD", minutes=round(breach, 1), reason="within 5 min of what riders were promised")
        elif breach >= HOLD_BAND_MIN:
            rec.update(verdict="PUSH_LATE", minutes=round(breach, 1),
                      reason=f"projected to reach the next unserved stop {breach:.0f} min after the promised time")
        else:
            rec.update(verdict="HOLD", minutes=round(breach, 1), reason="running ahead of the promised time")

        out.append(rec)

    return pd.DataFrame(out)
