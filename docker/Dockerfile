FROM python:3.11-slim@sha256:a5b427ace4900267d93db34138e512325c6fa6af84ad5e4ed5f3b36258cc4142

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
