# TODO (Phase 5): Pin to digest for reproducibility, e.g.:
# FROM python:3.11-slim@sha256:<digest>
# Run: docker pull python:3.11-slim && docker inspect python:3.11-slim | grep Id
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY migrations/ ./migrations/

# Create non-root user for security
RUN useradd -m -u 1000 botuser && \
    mkdir -p /data && \
    chown botuser:botuser /data

USER botuser

# Health check: verifies the bot is writing its heartbeat file (Phase 4: main loop touches this)
# File must exist and be written within the last 120 seconds
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os,time; f='/tmp/all247_heartbeat'; exit(0 if os.path.exists(f) and time.time()-os.path.getmtime(f)<120 else 1)"

CMD ["python", "-m", "bot.main"]
