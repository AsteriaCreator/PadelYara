# Railway Eversports microservice
# Build context = Backend/ (Railway Root Directory setting)
# All COPY paths are relative to Backend/.

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Build context is the repo root; files are under Backend/
COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install the Playwright Chromium browser for the pip-installed version.
# System dependencies are already in the base image; no --with-deps needed.
RUN python -m playwright install chromium

# Verify key imports at build time — catches missing libs before deploy
RUN python -c "from curl_cffi.requests import AsyncSession; from fastapi import FastAPI; import uvicorn; print('[build] imports OK')"

COPY Backend/eversports_service.py ./eversports_service.py

# Railway injects $PORT at runtime; default to 8000 for local runs
ENV PORT=8000
EXPOSE 8000

# Shell form so ${PORT} expands correctly at runtime
CMD ["sh", "-c", "python -m uvicorn eversports_service:app --host 0.0.0.0 --port ${PORT:-8000}"]
