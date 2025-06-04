from flask import Flask, render_template, request
from prometheus_client import Counter, Summary, generate_latest
import logging
import sys
import time
import random

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import get_current_span

# --- Setup Logging with Trace Context ---
class TraceFormatter(logging.Formatter):
    def format(self, record):
        span = get_current_span()
        context = span.get_span_context()
        record.trace_id = format(context.trace_id, "032x") if context.trace_id else "N/A"
        record.span_id = format(context.span_id, "016x") if context.span_id else "N/A"
        return super().format(record)

formatter = TraceFormatter("%(asctime)s [%(levelname)s] trace_id=%(trace_id)s span_id=%(span_id)s %(message)s")

handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# --- Setup Tracing ---
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces"))
trace.get_tracer_provider().add_span_processor(span_processor)

# --- Setup Flask App ---
app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

# --- Prometheus Metrics ---
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint"])
REQUEST_LATENCY = Summary("http_request_duration_seconds", "Request latency in seconds", ["endpoint"])

@app.route("/")
@REQUEST_LATENCY.labels(endpoint="/").time()
def home():
    REQUEST_COUNT.labels(method=request.method, endpoint="/").inc()
    logger.info("Visited home page")
    return render_template("index.html")

@app.route("/checkout")
@REQUEST_LATENCY.labels(endpoint="/checkout").time()
def checkout():
    REQUEST_COUNT.labels(method=request.method, endpoint="/checkout").inc()
    logger.info("Checkout page accessed")
    return render_template("checkout.html")

@app.route("/purchase", methods=["POST"])
@REQUEST_LATENCY.labels(endpoint="/purchase").time()
def purchase():
    REQUEST_COUNT.labels(method=request.method, endpoint="/purchase").inc()

    # Simulate optional error using query param ?error=true
    if request.args.get("error") == "true":
        logger.error("Simulated error occurred during purchase")
        raise ValueError("Simulated error for testing observability")

    amount = round(random.uniform(10.0, 100.0), 2)
    logger.info(f"User purchased item worth ${amount}")
    return render_template("thankyou.html", amount=amount)

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
