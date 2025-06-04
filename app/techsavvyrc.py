"""
This app is named **TechSavvyRC** and built specifically for demonstration and learning purposes.

This is a microservice-style Flask application created for hands-on learning of observability.
It integrates the following capabilities:

1. Metrics Collection:
   - Exposes Prometheus-compatible metrics via a '/metrics' endpoint.
   - Types used:
     - Counter: Tracks number of HTTP requests.
     - Summary: Captures request durations (e.g., average, quantiles).
     - Histogram: Buckets request durations into defined ranges.

   - Metrics can be:
     - Scraped directly by Prometheus
     - Forwarded to Elasticsearch using Metricbeat or via OpenTelemetry Collector (if configured)

2. Distributed Tracing using OpenTelemetry:
   - Automatically creates trace spans for Flask routes.
   - Exports traces to an OpenTelemetry Collector.
   - From there, traces can be forwarded to:
     - Elastic APM
     - Jaeger (optional)
     - Tempo (optional)
     - Any other OTLP-compatible tracing backend

3. Logging with Trace Context:
   - Custom logger includes 'trace_id' and 'span_id' in each log line.
   - Logs are written to stdout for easy container collection.
   - Logs can be shipped to:
     - Elasticsearch via Filebeat
     - Elastic APM (if using OpenTelemetry Collector with a log pipeline)

4. Observability Features for Testing:
   - Simulates random delays and errors to validate monitoring setups.
   - Error injection via '/purchase?error=true'
   - Clean observability workflow for metric, trace, and log correlation

You can observe:
- Metrics in Prometheus, Grafana, or Elastic
- Traces in Elastic APM
- Logs via Filebeat → Elasticsearch or other log backends
"""

# ---------------- Flask Web Framework ----------------
# Flask is used to define the web server and HTTP routes.
from flask import Flask, render_template, request

# ---------------- Prometheus Metrics ----------------
# Prometheus metric types used for observability.
from prometheus_client import Counter, Summary, Histogram, generate_latest

# ---------------- Standard Python Libraries ----------------
import logging      # For structured logging
import sys          # To send logs to stdout
import time         # Used internally by metrics
import random       # To simulate random purchase amounts

# ---------------- OpenTelemetry Tracing ----------------
# Used to define tracing capabilities and export them.
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

# Auto-instrumentation for Flask
from opentelemetry.instrumentation.flask import FlaskInstrumentor
# Utility to fetch the current active span for trace context
from opentelemetry.trace import get_current_span

# ======================================================
# Custom Logging Formatter to Include Trace Context
# ======================================================

class TraceFormatter(logging.Formatter):
    """
    A logging formatter that appends OpenTelemetry trace_id and span_id
    to each log line. This helps correlate logs with distributed traces.
    """

    def format(self, record):
        span = get_current_span()
        context = span.get_span_context()

        # Add trace_id and span_id to the log record
        record.trace_id = format(context.trace_id, "032x") if context.trace_id else "N/A"
        record.span_id = format(context.span_id, "016x") if context.span_id else "N/A"

        return super().format(record)

# Configure the format of the logs (includes timestamp, log level, trace context)
formatter = TraceFormatter(
    "%(asctime)s [%(levelname)s] trace_id=%(trace_id)s span_id=%(span_id)s %(message)s"
)

# Output logs to stdout so tools like Docker or Filebeat can pick them up
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

# Apply logger configuration to the root logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# ======================================================
# OpenTelemetry Tracer Configuration
# ======================================================

# Set up a tracer provider
trace.set_tracer_provider(TracerProvider())

# Create a tracer instance (used to start spans)
tracer = trace.get_tracer(__name__)

# Configure the exporter that sends spans to OpenTelemetry Collector (OTLP endpoint)
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces")
)

# Register the span processor with the tracer
trace.get_tracer_provider().add_span_processor(span_processor)

# ======================================================
# Flask Application Initialization
# ======================================================

# Initialize the Flask web application
app = Flask(__name__)

# Automatically instrument all Flask routes with tracing spans
FlaskInstrumentor().instrument_app(app)

# ======================================================
# Define Prometheus Metrics
# ======================================================

# Counter: counts all HTTP requests by method and endpoint
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests received",
    ["method", "endpoint"]
)

# Summary: calculates request durations (mean, quantiles)
REQUEST_LATENCY_SUMMARY = Summary(
    "http_request_duration_seconds_summary",
    "Latency summary of HTTP requests",
    ["endpoint"]
)

# Histogram: buckets durations into defined ranges for latency distribution
REQUEST_LATENCY_HISTOGRAM = Histogram(
    "http_request_duration_seconds_histogram",
    "Histogram of request duration in seconds",
    ["endpoint"],
    buckets=[0.1, 0.3, 0.5, 1, 2.5, 5, 10]  # Custom latency buckets
)

# ======================================================
# HTTP Route: Home Page
# ======================================================

@app.route("/")
@REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/").time()  # Decorator for automatic timing
def home():
    """
    Home page endpoint.
    This route serves the homepage UI.
    Tracks latency via histogram, increments request count, logs access.
    Handles GET request to '/'.
    - Increments request counter.
    - Records request latency.
    - Logs trace-aware access.
    - Renders the homepage template.
    """
    REQUEST_COUNT.labels(method=request.method, endpoint="/").inc()

    with REQUEST_LATENCY_SUMMARY.labels(endpoint="/").time(), \
         REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/").time():
        logger.info("Visited home page")
        return render_template("index.html")

# ======================================================
# HTTP Route: Checkout Page
# ======================================================

@app.route("/checkout")
@REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/checkout").time()
def checkout():
    """
    Checkout page endpoint.
    Used to simulate service call chains in distributed tracing.
    Tracks request count and latency.
    Handles GET request to '/checkout'.
    - Increments request counter.
    - Records request latency.
    - Logs checkout page access.
    - Renders the checkout template.
    """
    REQUEST_COUNT.labels(method=request.method, endpoint="/checkout").inc()

    with REQUEST_LATENCY_SUMMARY.labels(endpoint="/checkout").time(), \
         REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/checkout").time():
        logger.info("Checkout page accessed")
        return render_template("checkout.html")

# ======================================================
# HTTP Route: Purchase Page (Simulates Errors)
# ======================================================

@app.route("/purchase", methods=["POST"])
@REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/purchase").time()
def purchase():
    """
    Purchase endpoint (POST only).
    Simulates a business transaction and allows optional error simulation using ?error=true.
    Tracks request count, latency, and logs both success and error states.
    Handles POST request to '/purchase'.
    - Increments request counter.
    - Injects optional error if ?error=true.
    - Simulates a purchase and logs the amount.
    - Renders the thank-you template with purchase amount.
    """
    REQUEST_COUNT.labels(method=request.method, endpoint="/purchase").inc()

    with REQUEST_LATENCY_SUMMARY.labels(endpoint="/purchase").time(), \
         REQUEST_LATENCY_HISTOGRAM.labels(endpoint="/purchase").time():

        # Simulated error for testing observability pipelines
        if request.args.get("error") == "true":
            logger.error("Simulated error occurred during purchase")
            raise ValueError("Simulated error for testing observability")

        # Simulate a random purchase amount between $10 and $100
        amount = round(random.uniform(10.0, 100.0), 2)
        logger.info(f"User purchased item worth ${amount}")

        return render_template("thankyou.html", amount=amount)

# ======================================================
# HTTP Route: Prometheus Metrics Endpoint
# ======================================================

@app.route("/metrics")
def metrics():
    """
    Prometheus metrics scraping endpoint.
    Exposes all application metrics in Prometheus-compatible format.
    """
    return generate_latest(), 200, {"Content-Type": "text/plain"}

# ======================================================
# Run Flask Web Server
# ======================================================

if __name__ == "__main__":
    # Run the web app on all interfaces on port 8000 (suitable for Docker deployment)
    app.run(host="0.0.0.0", port=8000)
