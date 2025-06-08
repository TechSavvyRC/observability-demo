# --------------------------------------------------------------------------------
# Dockerfile for TechSavvyRC Flask Application
#
# This Dockerfile builds a secure, maintainable container:
#   - Uses python:3.11-slim
#   - Creates a non-root user (UID 472)
#   - Installs dependencies from requirements.txt
#   - Creates /var/log and the required log file with correct ownership
#   - Exposes port 8000 and sets a HEALTHCHECK
#   - Runs Flask app as non-root
# --------------------------------------------------------------------------------

# 1. Base image
FROM python:3.11-slim

# 2. Set working directory
WORKDIR /app

# 3. Create a non-root user 'appuser' (UID 472) to run the app
RUN groupadd --system appuser && \
    useradd --system --gid appuser --create-home --home-dir /app appuser

# 4. Copy only requirements.txt first (for caching)
COPY requirements.txt .

# 5. Install Python dependencies (no cache)
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copy all application code into the image
COPY . .

# 7. Create log directory and log file, set ownership to appuser
RUN mkdir -p /app/log && \
    touch /app/log/techsavvyrc.log && \
    chown -R appuser:appuser /app/log/techsavvyrc.log && \
    chmod 666 /app/log/techsavvyrc.log

# 8. Expose Flask port
EXPOSE 8000

# 9. Environment variables (for Flask logging & OTel)
ENV LOG_FILE=/app/log/techsavvyrc.log \
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318/v1/traces \
    PYTHONUNBUFFERED=1

# 10. Switch to non-root user
USER appuser

# 11. Healthcheck (check /metrics every 30s)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl --fail http://localhost:8000/metrics || exit 1

# 12. Default command to run the Flask app
CMD ["python", "techsavvyrc.py"]
