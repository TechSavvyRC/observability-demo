"""
This app is named "TechSavvyRC" and built specifically for demonstration and learning purposes.

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

# ---------------- Standard Python Libraries ----------------
import logging      # For structured logging
import sys          # To send logs to stdout
import time         # Used internally by metrics
import random       # To simulate random purchase amounts
import os
import signal       # For graceful shutdown on SIGTERM/SIGINT

# ---------------- Flask Web Framework ----------------
# Flask is used to define the web server and HTTP routes.
from flask import Flask, render_template, request, make_response

# ---------------- Prometheus Metrics ----------------
# Prometheus metric types used for observability.
from prometheus_client import Counter, Summary, Histogram, generate_latest

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

# ---------------------- Configuration ----------------------
# Name of the service, used in logs and metrics
SERVICE_NAME = "techsavvyrc"
# OTLP endpoint for sending spans to the OpenTelemetry Collector
# Default: http://otel-collector:4318/v1/traces
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318/v1/traces")
# Logging configuration
# LOG_LEVEL: INFO (default), DEBUG, WARNING, etc.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
# LOG_FILE: path to the file where logs will be written
LOG_FILE = os.getenv("LOG_FILE", "/app/log/techsavvyrc.log")

# ---------------------- Logging Setup ----------------------
# Create a logger named after the service
logger = logging.getLogger(SERVICE_NAME)
logger.setLevel(LOG_LEVEL)


# ======================================================
# Custom Logging Formatter to Include Trace Context
# ======================================================
class TraceFormatter(logging.Formatter):
    """
    Custom logging formatter that injects the current OpenTelemetry trace_id and span_id
    into each log record. This helps correlate logs with traces in centralized systems
    like Elasticsearch and Kibana’s APM UI.
    """
    def format(self, record):
        # Retrieve the current active span (if any)
        span = get_current_span()
        ctx = span.get_span_context() if span else None

        # If there is a valid span context, format trace_id and span_id as hex strings
        if ctx and ctx.trace_id:
            record.trace_id = f"{ctx.trace_id:032x}"
        else:
            record.trace_id = "N/A"

        if ctx and ctx.span_id:
            record.span_id = f"{ctx.span_id:016x}"
        else:
            record.span_id = "N/A"

        # Use the parent class to format the message, now including trace_id/span_id
        return super().format(record)

# Configure the format of the logs (includes timestamp, log level, trace context)
formatter = TraceFormatter(
    "%(asctime)s [%(levelname)s] service=%(name)s trace_id=%(trace_id)s span_id=%(span_id)s %(message)s"
)

# Ensure /app/log exists and is writable inside the container (handle in Dockerfile)
# FileHandler: writes logs to a file for persistent storage
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# StreamHandler: writes logs to stdout (useful in containerized environments)
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)


# ======================================================
# OpenTelemetry Tracer Configuration
# ======================================================
# Initialize the global tracer provider (OpenTelemetry SDK)
trace.set_tracer_provider(TracerProvider())

# Attempt to set up the OTLP exporter and a batch processor to send spans
span_processor = None
try:
    # Create an OTLP HTTP exporter that sends spans to the OTLP_ENDPOINT
    otlp_exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT)
    # BatchSpanProcessor collects spans and periodically sends them in batches
    span_processor = BatchSpanProcessor(otlp_exporter)
    trace.get_tracer_provider().add_span_processor(span_processor)
    logger.info(f"Tracing initialized with endpoint: {OTLP_ENDPOINT}")
except Exception as e:
    # If anything goes wrong (e.g., network issues), log an error and continue without tracing
    logger.error(f"Tracing initialization failed: {str(e)}")

# Obtain a named tracer for creating manual spans when needed
tracer = trace.get_tracer(SERVICE_NAME)


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
    ["method", "path", "status"]
)

# Histogram: buckets durations into defined ranges for latency distribution
REQUEST_DURATION_HISTOGRAM = Histogram(
    "http_request_duration_seconds_histogram",
    "Histogram of request latency distribution in seconds",
    ["path"],
    buckets=[0.1, 0.3, 0.5, 1, 2.5, 5, 10]
)

# Summary: calculates request durations (mean, quantiles)
REQUEST_DURATION_QUANTILES = Summary(
    "http_request_duration_seconds_summary",
    "Request latency quantile summary in seconds",
    ["path"]
)


# ======================================================
# Normalize Request Paths
# ======================================================
def normalize_path(path):
    """
    Normalize request paths to reduce high-cardinality in metrics.
    - If path begins with "/static", collapse to "/static"
    - If path begins with "/api", collapse to "/api/*"
    - Otherwise, return the path unchanged.
    """
    if path.startswith("/static"):
        return "/static"
    if path.startswith("/api"):
        return "/api/*"
    return path


# ======================================================
# Define Decorator for Timing Routes
# ======================================================
def observe_latency(func):
    """
    Decorator that measures request latency, records it into both a Histogram and
    a Summary. Also increments the request counter with status code, method, and path.
    Paths are normalized via normalize_path() to reduce metric cardinality.
    """
    def wrapper(*args, **kwargs):
        # Capture the incoming request’s normalized path
        raw_path   = request.path
        normalized = normalize_path(raw_path)
        method     = request.method

        # Record the start time for latency measurement
        start_time = time.time()
        # Initialize status code in case of exception
        status_code = 500

        try:
            # Execute the actual route function
            response = func(*args, **kwargs)

            # If the route returns a Flask Response or tuple, derive the status code
            if isinstance(response, tuple):
                # Tuple can be (body, status, headers) or (body, status)
                if len(response) >= 2 and isinstance(response[1], int):
                    status_code = response[1]
                else:
                    status_code = 200  # Default if no explicit status
            else:
                # If it’s a Response object, extract its status code
                try:
                    status_code = response.status_code
                except Exception:
                    status_code = 200

            return response
        except Exception:
            # Any exception leads here. We still want to record the counter and latency.
            status_code = 500
            # Re‐raise exception after recording metrics
            raise
        finally:
            # Stop timer and compute duration
            duration = time.time() - start_time

            # Record into Histogram and Summary
            REQUEST_DURATION_HISTOGRAM.labels(path=normalized).observe(duration)
            REQUEST_DURATION_QUANTILES.labels(path=normalized).observe(duration)

            # Increment the request counter including status code
            REQUEST_COUNT.labels(method=method, path=normalized, status=str(status_code)).inc()

    # Preserve function name and docstring
    wrapper.__name__ = func.__name__
    wrapper.__doc__  = func.__doc__
    return wrapper


# ======================================================
# Error Handler
# ======================================================
@app.errorhandler(Exception)
def handle_error(e):
    """
    Global error handler that catches any uncaught exception in a route,
    logs the error (with stack trace) including trace context, and returns
    a generic 500 Internal Server Error response.
    """
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    # Return a simple 500 response
    return make_response("Internal Server Error", 500)


# ======================================================
# HTTP Route: Home Page
# ======================================================
@app.route("/")
@observe_latency
def home():
    """
    Home page endpoint.
    - Normalizes the path.
    - Increments request counter via decorator.
    - Logs an INFO message indicating that the home page was accessed.
    - Returns the "index.html" template.
    """
    logger.info("Home page accessed")
    return render_template("index.html")


# ======================================================
# HTTP Route: Checkout Page
# ======================================================
@app.route("/checkout")
@observe_latency
def checkout():
    """
    Checkout page endpoint.
    - Normalizes the path.
    - Increments request counter via decorator.
    - Logs an INFO message indicating that the checkout page was accessed.
    - Returns the "checkout.html" template.
    """
    logger.info("Checkout page accessed")
    return render_template("checkout.html")


# ======================================================
# HTTP Route: Purchase Page (Simulates Errors)
# ======================================================
@app.route("/purchase", methods=["POST"])
@observe_latency
def purchase():
    """
    Purchase processing endpoint. Demonstrates:
      - Error simulation (triggered via ?error=true).
      - Random purchase amount calculation inside a manual child span.
      - Logging of purchase results or simulated errors.
      - Returns "thankyou.html" with the purchase amount on success.
    """
    # Check if the client requested an error simulation
    if request.args.get("error") == "true":
        # Log at ERROR level, include trace context
        logger.error("Simulated purchase error triggered")

        # Raise an exception to be handled by @app.errorhandler
        raise ValueError("Simulated error for observability testing")

    # Start a manual child span for the purchase amount calculation
    with tracer.start_as_current_span("calculate_purchase_amount"):
        # Generate a random amount between $10.00 and $100.00, rounded to 2 decimals
        amount = round(random.uniform(10.0, 100.0), 2)

    # Log success, including the calculated amount
    logger.info(f"Purchase completed successfully: ${amount}")
    # Render the thank-you page, passing "amount" to the template context
    return render_template("thankyou.html", amount=amount)


# ======================================================
# HTTP Route: Prometheus Metrics Endpoint
# ======================================================
@app.route("/metrics")
def metrics():
    """
    Prometheus scrape endpoint.
    - Normalizes the path.
    - The @observe_latency decorator is NOT used here, so latency is not recorded.
    - Increments the request counter via explicit call.
    - Returns the combined metrics from all Counter, Histogram, and Summary in text format.
    """
    normalized = normalize_path(request.path)
    REQUEST_COUNT.labels(method=request.method, path=normalized, status="200").inc()
    # Return metrics in text/plain so Prometheus or Metricbeat can scrape
    return generate_latest(), 200, {"Content-Type": "text/plain"}


# ======================================================
# Graceful Shutdown
# ======================================================
def shutdown_handler(signum, frame):
    """
    Handles SIGTERM/SIGINT signals to gracefully shut down the application.
    Specifically, shuts down the OpenTelemetry span processor to flush any buffered spans.
    """
    logger.info("Received shutdown signal, shutting down gracefully...")
    try:
        # If we set up a BatchSpanProcessor, call its shutdown() method
        if span_processor:
            span_processor.shutdown()
            logger.info("OpenTelemetry span processor shut down successfully.")
    except Exception as e:
        logger.error(f"Error during span processor shutdown: {str(e)}")
    # Exit the process
    sys.exit(0)

# Register the shutdown handler for SIGTERM and SIGINT
signal.signal(signal.SIGTERM, shutdown_handler)
signal.signal(signal.SIGINT, shutdown_handler)


# ======================================================
# Main Entry Point: Run Flask Web Server
# ======================================================
def main():
    """
    Main function to start the Flask application.
    Always run with 'python techsavvyrc.py' or configure with a WSGI server in production.
    """
    logger.info(f"Starting {SERVICE_NAME} service on port 8000")
    # app.run is the Flask development server. In production, use Gunicorn or similar.
    app.run(host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
