import time
import requests
from datetime import datetime

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather code → (icon, german description)
_WMO: dict[int, tuple[str, str]] = {
    0:  ("sun",     "Klar"),
    1:  ("sun",     "Überwiegend klar"),
    2:  ("cloud",   "Teils bewölkt"),
    3:  ("cloud",   "Bedeckt"),
    45: ("fog",     "Nebel"),
    48: ("fog",     "Reifnebel"),
    51: ("drizzle", "Leichter Nieselregen"),
    53: ("drizzle", "Nieselregen"),
    55: ("drizzle", "Starker Nieselregen"),
    61: ("rain",    "Leichter Regen"),
    63: ("rain",    "Regen"),
    65: ("rain",    "Starker Regen"),
    71: ("snow",    "Leichter Schneefall"),
    73: ("snow",    "Schneefall"),
    75: ("snow",    "Starker Schneefall"),
    77: ("snow",    "Schneekörner"),
    80: ("rain",    "Leichte Regenschauer"),
    81: ("rain",    "Regenschauer"),
    82: ("rain",    "Starke Regenschauer"),
    85: ("snow",    "Schneeschauer"),
    86: ("snow",    "Starke Schneeschauer"),
    95: ("thunder", "Gewitter"),
    96: ("thunder", "Gewitter mit Hagel"),
    99: ("thunder", "Gewitter mit starkem Hagel"),
}


def _wmo_to_weather(code: int, temp: float, rain_prob: int) -> dict:
    icon, desc = _WMO.get(code, ("cloud", "Unbekannt"))
    return {
        "icon":      icon,
        "desc":      desc,
        "temp":      temp,
        "rain_prob": rain_prob,
        "code":      code,
    }


def get_weather_for_hour(lat: float, lon: float, dt: datetime, retries: int = 3) -> dict | None:
    params = {
        "latitude":      lat,
        "longitude":     lon,
        "hourly":        "temperature_2m,precipitation_probability,weathercode",
        "forecast_days": 7,
        "timezone":      "Europe/Vienna",
    }
    target = dt.strftime("%Y-%m-%dT%H:00")

    for attempt in range(retries):
        try:
            resp = requests.get(OPEN_METEO_URL, params=params, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            times = data["hourly"]["time"]
            if target not in times:
                return None
            i = times.index(target)
            return _wmo_to_weather(
                code=data["hourly"]["weathercode"][i],
                temp=data["hourly"]["temperature_2m"][i],
                rain_prob=data["hourly"]["precipitation_probability"][i],
            )
        except Exception:
            if attempt < retries - 1:
                time.sleep(1)

    return None
