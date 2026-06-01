import time
import httpx
from datetime import datetime, timezone
from typing import TypedDict
from zoneinfo import ZoneInfo


class WeatherResult(TypedDict):
    icon:      str   # "sun" | "cloud" | "fog" | "rain" | "drizzle" | "snow" | "thunder"
    desc:      str   # German description e.g. "Sonnig"
    temp:      float # °C
    rain_prob: int   # 0–100

_WEATHER_CACHE: dict = {}
_WEATHER_TTL = 900  # 15 minutes

MET_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
# met.no requires a descriptive User-Agent identifying the application
MET_UA  = "PadelYara/1.0 github.com/AsteriaCreator/NeoPadelChecker"

# ZoneInfo handles CET/CEST transitions automatically (UTC+1 in winter, UTC+2 in summer)
_VIENNA_TZ = ZoneInfo("Europe/Vienna")

_SYMBOL_TO_ICON: dict[str, str] = {
    "clearsky":        "sun",
    "fair":            "sun",
    "partlycloudy":    "cloud",
    "cloudy":          "cloud",
    "fog":             "fog",
    "lightrainshowers":   "rain",
    "rainshowers":        "rain",
    "heavyrainshowers":   "rain",
    "lightrain":       "rain",
    "rain":            "rain",
    "heavyrain":       "rain",
    "lightdrizzle":    "drizzle",
    "drizzle":         "drizzle",
    "lightsleet":      "rain",
    "sleet":           "rain",
    "heavysleet":      "rain",
    "lightsnow":       "snow",
    "snow":            "snow",
    "heavysnow":       "snow",
    "snowshowers":     "snow",
    "thunder":         "thunder",
    "lightrainandthunder":  "thunder",
    "rainandthunder":       "thunder",
    "heavyrainandthunder":  "thunder",
    "sleetandthunder":      "thunder",
}

_ICON_DESC: dict[str, str] = {
    "sun":     "Sonnig",
    "cloud":   "Bewölkt",
    "fog":     "Neblig",
    "rain":    "Regen",
    "drizzle": "Nieselregen",
    "snow":    "Schnee",
    "thunder": "Gewitter",
}


def _symbol_to_icon(code: str) -> str:
    """Strip _day/_night suffix then match."""
    base = code.replace("_day", "").replace("_night", "").replace("_polartwilight", "")
    return _SYMBOL_TO_ICON.get(base, "cloud")


def _precip_to_rain_prob(mm: float, symbol: str) -> int:
    """Estimate rain probability from precipitation amount + symbol code."""
    if mm > 2.0:   return 90
    if mm > 0.5:   return 70
    if mm > 0.1:   return 40
    if mm > 0.0:   return 20
    # No precipitation expected — check if symbol implies rain chance
    icon = _symbol_to_icon(symbol)
    if icon in ("rain", "drizzle", "thunder"): return 60
    if icon == "snow":   return 50
    if icon == "cloud":  return 10
    return 0


def _cache_key(lat: float, lon: float, dt: datetime) -> str:
    return f"{lat:.4f},{lon:.4f}*{dt.strftime('%Y-%m-%d')}*{dt.strftime('%H:00')}"


async def get_weather_for_hour(
    client: httpx.AsyncClient, lat: float, lon: float, dt: datetime
) -> WeatherResult | None:
    key = _cache_key(lat, lon, dt)
    now = time.time()
    entry = _WEATHER_CACHE.get(key)
    if entry and now - entry["timestamp"] < _WEATHER_TTL:
        return entry["weather"]

    # Convert Vienna local time → UTC for matching met.no timeseries
    dt_utc = dt.replace(tzinfo=_VIENNA_TZ).astimezone(timezone.utc)
    target = dt_utc.strftime("%Y-%m-%dT%H:00:00Z")

    try:
        resp = await client.get(
            MET_URL,
            params={"lat": round(lat, 4), "lon": round(lon, 4)},
            headers={"User-Agent": MET_UA},
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()

        timeseries = data["properties"]["timeseries"]
        slot = next((t for t in timeseries if t["time"] == target), None)
        if slot is None:
            # Target hour is likely in the past — fall back to the first available slot
            slot = timeseries[0] if timeseries else None
        if slot is None:
            return None

        instant  = slot["data"]["instant"]["details"]
        next_1h  = slot["data"].get("next_1_hours") or slot["data"].get("next_6_hours") or {}
        summary  = next_1h.get("summary", {})
        details  = next_1h.get("details", {})

        symbol   = summary.get("symbol_code", "cloudy")
        precip   = float(details.get("precipitation_amount", 0))
        icon     = _symbol_to_icon(symbol)
        temp     = round(instant["air_temperature"], 1)
        rain_prob = _precip_to_rain_prob(precip, symbol)

        weather = {
            "icon":      icon,
            "desc":      _ICON_DESC.get(icon, "Bewölkt"),
            "temp":      temp,
            "rain_prob": rain_prob,
        }
        _WEATHER_CACHE[key] = {"weather": weather, "timestamp": now}
        return weather

    except httpx.RequestError as exc:
        print(f"[weather] request error: {type(exc).__name__}: {exc}")
        return None
    except httpx.HTTPStatusError as exc:
        print(f"[weather] HTTP {exc.response.status_code}: {exc}")
        return None
