import math


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def filter_by_radius(
    venues: list[dict], lat: float, lon: float, radius_km: float
) -> list[dict]:
    """Return venues within radius_km, each annotated with distance_km."""
    result = []
    for v in venues:
        if v.get("lat") is None or v.get("lon") is None:
            continue
        d = haversine_km(lat, lon, v["lat"], v["lon"])
        if d <= radius_km:
            result.append({**v, "distance_km": round(d, 1)})
    return result
