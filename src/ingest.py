"""Load the five CSVs and repair the one known data-quality issue.

`recorded_at` is the device clock. One ping (P-0001797) has an impossible
value (minute=60). We repair it using received_at minus that vehicle's
median clock skew, rather than dropping it -- dropping would leave a bigger
gap in the trace than the corruption itself. See eda_full.ipynb section 2
for the discovery and the reasoning.
"""
import pandas as pd


def load(data_dir="data"):
    routes = pd.read_csv(f"{data_dir}/routes.csv")
    stops = pd.read_csv(f"{data_dir}/stops.csv")

    trips = pd.read_csv(f"{data_dir}/trips.csv", parse_dates=["scheduled_start", "scheduled_end"])
    trips["service_date"] = pd.to_datetime(trips["service_date"]).dt.date

    bookings = pd.read_csv(f"{data_dir}/bookings.csv", parse_dates=["booked_at", "promised_eta"])

    pings_raw = pd.read_csv(f"{data_dir}/gps_pings.csv")
    recorded = pd.to_datetime(pings_raw["recorded_at"], errors="coerce")
    received = pd.to_datetime(pings_raw["received_at"], errors="coerce")
    bad_mask = recorded.isna()

    pings = pings_raw.copy()
    pings["recorded_at"] = recorded
    pings["received_at"] = received
    pings["recorded_at_was_repaired"] = bad_mask

    skew_s = (pings.loc[~bad_mask, "received_at"] - pings.loc[~bad_mask, "recorded_at"]).dt.total_seconds()
    median_skew_by_vehicle = (
        pings.loc[~bad_mask].assign(skew=skew_s).groupby("vehicle_id")["skew"].median()
    )
    for i in pings.index[bad_mask]:
        v = pings.at[i, "vehicle_id"]
        pings.at[i, "recorded_at"] = pings.at[i, "received_at"] - pd.Timedelta(
            seconds=median_skew_by_vehicle.get(v, 2)
        )

    vop = pings.groupby("vehicle_id")["operator_id"].first().to_dict()
    trips = trips.copy()
    trips["operator_id"] = trips.vehicle_id.map(vop)

    return dict(routes=routes, stops=stops, trips=trips, bookings=bookings, pings=pings)
