from math import asin, cos, radians, sin, sqrt


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def is_inside_geofence(
    user_lat: float,
    user_lon: float,
    dest_lat: float,
    dest_lon: float,
    radius_m: int,
    accuracy_m: float,
    dwell_seconds: int,
) -> tuple[bool, float]:
    distance = distance_m(user_lat, user_lon, dest_lat, dest_lon)
    effective_radius = radius_m + min(max(accuracy_m, 0), 80)
    verified = distance <= effective_radius and dwell_seconds >= 60
    return verified, distance
