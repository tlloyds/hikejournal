# Cloud Run entry point for the Android companion API.
#
# Keep this at the repository root so Cloud Run's GitHub connection can detect
# it without any custom build configuration. The matching Dockerfile in
# deploy/mobile remains available for hosts configured with that path.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MOBILE_REQUIRE_EXPLICIT_TOKEN=true \
    PORT=8080

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mobile_api.py ./
COPY hike_journal ./hike_journal

RUN useradd --create-home --uid 10001 hikejournal
USER hikejournal

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8080') + '/health', timeout=3)"

CMD ["sh", "-c", "uvicorn mobile_api:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
