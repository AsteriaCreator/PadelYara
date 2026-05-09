# Railway Eversports microservice
# Bakes Playwright Chromium into the image so the Cloudflare-bypass fallback
# is available at runtime without a per-startup download.

FROM python:3.12-slim

WORKDIR /app

# Install Python dependencies (cached layer — only invalidated when requirements change)
COPY Backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright Chromium and all required OS libraries.
# Must run as root; --with-deps handles the apt installs automatically.
RUN python -m playwright install --with-deps chromium

# Copy only the service module
COPY Backend/eversports_service.py ./eversports_service.py

# Railway injects $PORT at runtime; fall back to 8000 for local runs
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn eversports_service:app --host 0.0.0.0 --port ${PORT:-8000}"]
