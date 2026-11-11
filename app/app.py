import os, random, time
from flask import Flask, jsonify, request, g, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)
FAILURE_RATE = float(os.getenv("FAILURE_RATE", "0.05"))  # 5% random failures

REQUESTS = Counter("orderapi_http_requests_total", "Total HTTP requests",
                   ["method", "endpoint", "status"])
LATENCY = Histogram("orderapi_http_request_duration_seconds", "Request latency in seconds",
                    ["method", "endpoint"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5))
ORDERS_CREATED = Counter("orderapi_orders_created_total", "Orders created successfully")
ORDERS_FAILED = Counter("orderapi_orders_failed_total", "Orders that failed", ["reason"])

@app.before_request
def start_timer():
    g.start = time.perf_counter()

@app.after_request
def record_metrics(resp):
    # use the route pattern, not the raw URL, so labels stay few and bounded
    endpoint = request.url_rule.rule if request.url_rule else "unmatched"
    if endpoint != "/metrics":
        REQUESTS.labels(request.method, endpoint, str(resp.status_code)).inc()
        LATENCY.labels(request.method, endpoint).observe(time.perf_counter() - g.start)
    return resp

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.post("/api/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    item, qty = data.get("item"), data.get("quantity")
    if not item or not isinstance(qty, int) or qty < 1:
        ORDERS_FAILED.labels(reason="invalid_input").inc()
        return jsonify(error="item and a positive integer quantity are required"), 400

    time.sleep(random.uniform(0.01, 0.2))  # pretend to do work

    if request.args.get("fail") == "true" or random.random() < FAILURE_RATE:
        ORDERS_FAILED.labels(reason="internal_error").inc()
        app.logger.error("order failed item=%s", item)
        return jsonify(error="order processing failed"), 500

    ORDERS_CREATED.inc()
    return jsonify(status="created", order_id=int(time.time() * 1000)), 201

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, threaded=True)
