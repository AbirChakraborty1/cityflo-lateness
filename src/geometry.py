"""Distance-along-route, via the ordered stop polyline (haversine chain).

Coarse by construction -- a ping is projected onto its *nearest stop*, not
interpolated onto the road centreline. DATA_GUIDE.md is explicit that the
geometry isn't map-matched, so anything finer than "which stop segment is
this bus near" would be reading too much into it.
"""
import numpy as np


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlon / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


class RouteGeometry:
    def __init__(self, stops):
        st = stops.sort_values(["route_id", "seq"]).copy()
        st["prev_lat"] = st.groupby("route_id")["lat"].shift()
        st["prev_lon"] = st.groupby("route_id")["lon"].shift()
        st["seg_km"] = haversine_km(st.lat, st.lon, st.prev_lat, st.prev_lon).fillna(0)
        st["dist_km"] = st.groupby("route_id")["seg_km"].cumsum()
        self.stops = st
        self.route_len = st.groupby("route_id")["dist_km"].max().to_dict()
        self.last_seq = st.groupby("route_id")["seq"].max().to_dict()

    def progress(self, route_id, lat, lon):
        """Returns (distance_along_route_km, distance_to_nearest_stop_km, stop_seq)."""
        rs = self.stops[self.stops.route_id == route_id]
        d = haversine_km(lat, lon, rs.lat.values, rs.lon.values)
        j = int(np.argmin(d))
        return rs.dist_km.values[j], float(d[j]), int(rs.seq.values[j])

    def stop_dist_km(self, stop_id):
        row = self.stops.loc[self.stops.stop_id == stop_id]
        return float(row.dist_km.iloc[0])
