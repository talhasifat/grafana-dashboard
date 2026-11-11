import json

def panel(pid, title, targets, unit, x, y, w=8, h=8, kind="timeseries"):
    return {
        "id": pid, "type": kind, "title": title,
        "datasource": "Prometheus",
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "fieldConfig": {"defaults": {"unit": unit}, "overrides": []},
        "targets": [{"refId": chr(65 + i), "expr": e, "legendFormat": l,
                     "datasource": "Prometheus"} for i, (e, l) in enumerate(targets)],
    }

NET = 'device!~"lo|veth.*|docker.*|br-.*"'
panels = [
    panel(1, "CPU usage %",
          [('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)', "CPU %")], "percent", 0, 0),
    panel(2, "RAM usage %",
          [('(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100', "RAM %")], "percent", 8, 0),
    panel(3, "Disk usage % (/)",
          [('100 * (1 - node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"})', "Disk %")], "percent", 16, 0),
    panel(4, "Network throughput",
          [(f'sum(rate(node_network_receive_bytes_total{{{NET}}}[1m]))', "Receive"),
           (f'sum(rate(node_network_transmit_bytes_total{{{NET}}}[1m]))', "Transmit")], "Bps", 0, 8),
    panel(5, "Requests per second",
          [('sum by (endpoint) (rate(orderapi_http_requests_total[1m]))', "{{endpoint}}")], "reqps", 8, 8),
    panel(6, "Error rate % (5xx)",
          [('100 * sum(rate(orderapi_http_requests_total{status=~"5.."}[1m])) / sum(rate(orderapi_http_requests_total[1m]))', "Errors %")], "percent", 16, 8),
    panel(7, "p95 request latency",
          [('histogram_quantile(0.95, sum by (le) (rate(orderapi_http_request_duration_seconds_bucket[5m])))', "p95")], "s", 0, 16),
    panel(8, "Orders created / failed (per minute)",
          [('sum(increase(orderapi_orders_created_total[1m]))', "Created"),
           ('sum(increase(orderapi_orders_failed_total[1m]))', "Failed")], "short", 8, 16),
    panel(9, "Host uptime",
          [('node_time_seconds - node_boot_time_seconds', "Uptime")], "s", 16, 16, kind="stat"),
]

dash = {
    "uid": "observability-main", "title": "System & Application Observability",
    "schemaVersion": 27, "version": 1, "refresh": "10s",
    "time": {"from": "now-30m", "to": "now"},
    "panels": panels,
}
json.dump(dash, open("grafana/dashboards/observability.json", "w"), indent=2)
print("written", len(panels), "panels")
