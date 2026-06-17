import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from venues_mongo import load_venues
from weather import get_weather_for_hour
from routers.search import _parse_datetime

router = APIRouter()

DEFAULT_VENUE_ID = "padelzone-traiskirchen"


@router.get("/api/weather")
async def weather_endpoint(
    lat:  float = Query(),
    lon:  float = Query(),
    date: str | None = Query(default=None),
    time: str | None = Query(default=None),
):
    """Return hourly weather (temperature, rain probability, wind) for a given location and time."""
    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": parse_error})

    async with httpx.AsyncClient() as client:
        weather = await get_weather_for_hour(client, lat, lon, dt)
    if weather is None:
        return JSONResponse(status_code=502, content={"error": "weather_unavailable"})
    return weather


@router.get("/api/weather-test")
async def weather_test(
    venue_id: str | None = Query(default=None),
    date:     str | None = Query(default=None),
    time:     str | None = Query(default=None),
):
    """Dev/diagnostic: fetch weather for a specific venue by ID to verify the weather integration."""
    vid = venue_id or DEFAULT_VENUE_ID

    venue = next((v for v in await load_venues() if v["id"] == vid), None)
    if venue is None:
        return JSONResponse(status_code=404, content={"error": "venue_not_found", "venue_id": vid})

    if venue["lat"] is None or venue["lon"] is None:
        return JSONResponse(status_code=422, content={"error": "no_coordinates", "venue_id": vid})

    dt, parse_error = _parse_datetime(date, time)
    if parse_error:
        return JSONResponse(status_code=400, content={"error": "invalid_params", "detail": parse_error})

    async with httpx.AsyncClient() as client:
        weather = await get_weather_for_hour(client, venue["lat"], venue["lon"], dt)
    if weather is None:
        return JSONResponse(status_code=502, content={"error": "weather_unavailable", "venue_id": vid})

    return {
        "venue_id":       venue["id"],
        "venue_name":     venue["name"],
        "lat":            venue["lat"],
        "lon":            venue["lon"],
        "requested_time": dt.strftime("%Y-%m-%dT%H:%M"),
        "weather":        weather,
    }
