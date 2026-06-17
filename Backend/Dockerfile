# Consolidated PadelYara backend — eTennis + Eversports scrapers in one service
# Build context = repo root; Railway Root Directory should be set to /
# All COPY paths are relative to repo root.

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install the Playwright Chromium browser for the pip-installed version.
# System dependencies are already in the base image; no --with-deps needed.
RUN python -m playwright install chromium

# venues.py resolves CSV as Path(__file__).parent.parent / "Padel_Venues.csv"
# With WORKDIR /app that means /Padel_Venues.csv
COPY Padel_Venues.csv /Padel_Venues.csv

# Copy all Backend Python source files
COPY Backend/app.py               ./app.py
COPY Backend/eversports_service.py ./eversports_service.py
COPY Backend/etennis_checker.py   ./etennis_checker.py
COPY Backend/analytics.py         ./analytics.py
COPY Backend/venues.py            ./venues.py
COPY Backend/venues_mongo.py      ./venues_mongo.py
COPY Backend/weather.py           ./weather.py
COPY Backend/distance.py          ./distance.py
COPY Backend/eversports_prices.py ./eversports_prices.py
COPY Backend/tournaments_mongo.py  ./tournaments_mongo.py
COPY Backend/padel_austria_scraper.py ./padel_austria_scraper.py
COPY Backend/padel_austria_player.py ./padel_austria_player.py
COPY Backend/yara_urteil_prompt.py ./yara_urteil_prompt.py
COPY Backend/urteil_mongo.py      ./urteil_mongo.py
COPY Backend/bezirk_utils.py      ./bezirk_utils.py
COPY Backend/tennis04_checker.py  ./tennis04_checker.py
COPY Backend/availability.py      ./availability.py
COPY Backend/opening_hours.py     ./opening_hours.py
COPY Backend/state.py             ./state.py
COPY Backend/auth.py              ./auth.py
COPY Backend/scheduler.py         ./scheduler.py
COPY Backend/routers/             ./routers/

# Verify key imports at build time — catches missing libs before deploy
RUN python -c "from curl_cffi.requests import AsyncSession; from fastapi import FastAPI; import uvicorn; from eversports_service import check_eversports_slot; import eversports_prices; import tournaments_mongo; import padel_austria_scraper; import padel_austria_player; import yara_urteil_prompt; import urteil_mongo; import bezirk_utils; import tennis04_checker; import availability; import opening_hours; import state; import auth; import scheduler; import routers.search; import routers.analytics; import routers.tournaments; import routers.venues; import routers.weather; import routers.subscribers; import routers.urteil; import routers.admin; print('[build] imports OK')"

# Railway injects $PORT at runtime; default to 8000 for local runs
ENV PORT=8000
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Shell form so ${PORT} expands correctly at runtime
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
