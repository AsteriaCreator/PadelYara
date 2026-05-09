# Railway Eversports microservice
# Uses the official Microsoft Playwright Python image so all Chromium system
# dependencies are pre-installed and baked into the image.

FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# Install Python dependencies
COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install the Playwright Chromium browser for the exact pip-installed version.
# System dependencies are already in the base image; no --with-deps needed.
RUN python -m playwright install chromium

# Verify key imports work at build time — catches missing libs before deploy
RUN python -c "from curl_cffi.requests import AsyncSession; from fastapi import FastAPI; import uvicorn; print('[build] imports OK')"

# Copy only the service module
COPY Backend/eversports_service.py ./eversports_service.py

# Railway injects $PORT at runtime; default to 8000 for local runs
ENV PORT=8000
EXPOSE 8000

# Shell form so ${PORT} expands correctly at runtime
CMD ["sh", "-c", "uvicorn eversports_service:app --host 0.0.0.0 --port ${PORT:-8000}"]
