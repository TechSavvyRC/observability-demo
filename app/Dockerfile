FROM python:3.11-slim

WORKDIR /app
COPY . .
RUN pip install flask prometheus_client opentelemetry-sdk opentelemetry-exporter-otlp opentelemetry-instrumentation-flask
CMD ["python", "techsavvyrc.py"]
