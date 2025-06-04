from flask import Flask, render_template, request, redirect, url_for
from prometheus_client import Counter, Summary, generate_latest
import logging
import time
import random

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)
span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces", insecure=True))
trace.get_tracer_provider().add_span_processor(span_processor)

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

REQUEST_COUNT = Counter("http_requests_total", "Total HTTP Requests", ["method", "endpoint"])
REQUEST_LATENCY = Summary("http_request_duration_seconds", "Request latency in seconds", ["endpoint"])

@app.route("/")
@REQUEST_LATENCY.labels(endpoint="/").time()
def home():
    REQUEST_COUNT.labels(method=request.method, endpoint="/").inc()
    logging.info("Visited home page")
    return render_template("index.html")

@app.route("/checkout")
@REQUEST_LATENCY.labels(endpoint="/checkout").time()
def checkout():
    REQUEST_COUNT.labels(method=request.method, endpoint="/checkout").inc()
    logging.info("Checkout page accessed")
    return render_template("checkout.html")

@app.route("/purchase", methods=["POST"])
@REQUEST_LATENCY.labels(endpoint="/purchase").time()
def purchase():
    REQUEST_COUNT.labels(method=request.method, endpoint="/purchase").inc()
    amount = round(random.uniform(10.0, 100.0), 2)
    logging.info(f"User purchased item worth ${amount}")
    return render_template("thankyou.html", amount=amount)

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": "text/plain"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
