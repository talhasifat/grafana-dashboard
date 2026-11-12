# System & Application Observability: Practical Assessment

| | |
|---|---|
| **Candidate name** | `Talha Hossain Sifat` |
| **Candidate ID** | `30260` |
| **Instructor** | Lipton Ahammed |
| **Submission date** | 12 Nov 2026 |
| **GitHub URL** | `https://github.com/talhasifat/grafana-dashboardO` |

A working observability platform that collects **real host metrics**, **real HTTP application metrics**, **real Kubernetes pod logs**, shows them in **Grafana**, and sends an **email alert** when the application goes down.

<img width="1917" height="915" alt="Screenshot 2026-11-12 103231" src="https://github.com/user-attachments/assets/9ef437a0-fe8f-4dc2-967b-9910ce310c89" />


---

## 1. What this project delivers

| # | Outcome | How it is done |
|---|---|---|
| 1 | Live metrics | Node Exporter and the Order API are scraped by Prometheus every 15 s. Grafana shows CPU, RAM, disk, network, requests/s, error rate, p95 latency and business events. |
| 2 | Kubernetes logs | A MicroK8s workload writes to stdout/stderr. Grafana Alloy collects the pod logs and pushes them to Loki. Grafana Explore searches them with LogQL. |
| 3 | Email alerting | A Grafana alert rule (`OrderAPI target down`) fires after a controlled failure and Grafana sends an email through SMTP. |

---
<img width="2720" height="2192" alt="observability_architecture" src="https://github.com/user-attachments/assets/47c3b21a-fe5d-400a-b2f5-f7ebe7bec353" />

## 2. Architecture

```
METRICS
  Ubuntu VM --> Node Exporter ----\
                                   >--> Prometheus --> Grafana (PromQL dashboards)
  Order API (/metrics) -----------/

LOGS
  MicroK8s pod (stdout/stderr) --> Grafana Alloy --> Loki --> Grafana (Explore / LogQL)

ALERTING
  Grafana alert rule --> SMTP server --> recipient inbox
```

### Where things run

| Component | Where | Notes |
|---|---|---|
| Prometheus, Grafana, Loki, Node Exporter, Order API | Docker Compose in the VM | `compose.yaml` |
| Log-generating workload | MicroK8s, namespace `observability-demo` | `kubernetes/workload.yaml` |
| Grafana Alloy | MicroK8s, namespace `alloy` (Helm) | `kubernetes/alloy-values.yaml` |

### How logs travel from Kubernetes to Loki

Alloy runs inside MicroK8s, and Loki runs in Docker Compose on the same VM. Loki publishes its port **only on the Docker bridge address of the VM** (`172.17.0.1:3100`, set by `LOKI_BIND_IP` in `.env`). Pods can reach that address, but it is not exposed on any external interface. Alloy pushes logs to `http://172.17.0.1:3100/loki/api/v1/push`.

---

## 3. Deviations from the reference architecture

1. **Ubuntu 22.04 inside a Vagrant VM** is used instead of Ubuntu 26.04 directly on the laptop. All tools (Docker Engine, Docker Compose, MicroK8s, Helm) run natively inside this Ubuntu VM. The host metrics therefore describe the VM.
2. **Access from the laptop's browser uses an SSH tunnel** (see section 6) so that no observability port is published on a public interface.

---

## 4. Project structure

```
30260_observability/
├── README.md
├── compose.yaml
├── .env.example
├── .gitignore
├── app/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── prometheus/
│   └── prometheus.yml
├── loki/
│   └── config.yml
├── kubernetes/
│   ├── namespace.yaml
│   ├── workload.yaml
│   └── alloy-values.yaml
├── grafana/
│   ├── dashboards/
│   │   └── observability.json
│   └── provisioning/
│       ├── dashboards/dashboards.yml
│       └── datasources/datasources.yml
├── alerting/
│   ├── alert-rule.yaml
│   └── configuration-notes.md
├── scripts/
│   ├── make_dashboard.py
│   └── traffic-test.sh
└── evidence/
    └── (screenshots)
```

---

## 5. Prerequisites

- Ubuntu with **Docker Engine** and **Docker Compose v2**
- **MicroK8s** with the `dns`, `hostpath-storage` and `helm3` add-ons enabled
- Python 3 (only to regenerate the dashboard JSON)
- A Gmail account (or other SMTP provider) with an **app password** for the alert email

Verify the toolchain:

```bash
lsb_release -a
docker --version
docker compose version
microk8s status --wait-ready
microk8s kubectl get nodes
microk8s helm3 version
```

---

## 6. Setup

### 6.1 Configure environment variables

```bash
cd ~/30260_observability
cp .env.example .env
nano .env
```

`.env` holds the real values and is **never committed** (it is in `.gitignore`). `.env.example` contains placeholders only.

| Variable | Purpose |
|---|---|
| `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD` | Grafana admin login |
| `SMTP_HOST` | SMTP server and port, e.g. `smtp.gmail.com:587` |
| `SMTP_USER` | SMTP username |
| `SMTP_PASSWORD` | SMTP app password (secret) |
| `SMTP_FROM` | Sender address |
| `LOKI_BIND_IP` | Address Loki publishes on. Use `172.17.0.1` so MicroK8s pods can reach it. |

Check the Docker bridge address if unsure:

```bash
ip -4 addr show docker0 | grep inet
```

### 6.2 Start the Compose stack

```bash
docker compose config > /dev/null && echo "config OK"
docker compose up -d --build
docker compose ps
curl http://172.17.0.1:3100/ready        # prints: ready
```

Services: `app`, `node-exporter`, `prometheus`, `loki`, `grafana`. Data is stored in the named volumes `prometheus_data`, `loki_data` and `grafana_data`, and all services use `restart: unless-stopped`.

### 6.3 Deploy the Kubernetes workload

```bash
microk8s kubectl apply -f kubernetes/namespace.yaml
microk8s kubectl apply -f kubernetes/workload.yaml
microk8s kubectl get pods -n observability-demo
microk8s kubectl logs -n observability-demo deploy/log-generator --tail=10
```

The `log-generator` pod prints an `INFO` line every 2 seconds and an intentional `ERROR` line (to stderr) every 10th iteration.

### 6.4 Install Grafana Alloy

```bash
microk8s helm3 repo add grafana https://grafana.github.io/helm-charts
microk8s helm3 repo update
microk8s helm3 install alloy grafana/alloy -n alloy --create-namespace -f kubernetes/alloy-values.yaml
microk8s kubectl get pods -n alloy
microk8s kubectl logs -n alloy deploy/alloy -c alloy --tail=20
```

Alloy discovers pods, labels each log line with `namespace`, `pod`, `container` and `app`, and forwards the logs to Loki.

---

## 7. Access (private to the laptop)

All services listen on `127.0.0.1` inside the VM (Loki on the Docker bridge address). Nothing is published on a public interface. To open them from a Windows browser, use an SSH tunnel and keep that terminal open:

```powershell
vagrant ssh -- -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 -L 8000:127.0.0.1:8000
```

| Service | URL |
|---|---|
| Grafana | http://localhost:3000 (login from `.env`; default `admin` / `admin` on first start) |
| Prometheus | http://localhost:9090 |
| Order API | http://localhost:8000 |

Node Exporter (port 9100) and Loki (3100) are **not** forwarded to the laptop.

Grafana loads two data sources (Prometheus, Loki) and the dashboard automatically from `grafana/provisioning` and `grafana/dashboards`.

---

## 8. The Order API

Source: `app/app.py` (Flask and `prometheus_client`).

| Endpoint | Description |
|---|---|
| `GET /health` | Returns `{"status":"ok"}` |
| `POST /api/orders` | Body `{"item":"book","quantity":2}`. Returns `201` on success, `400` on invalid input, `500` on failure. Adding `?fail=true` forces a failure. A random failure rate is set by `FAILURE_RATE` (default 5 %). |
| `GET /metrics` | Prometheus metrics |

### Custom metrics

| Metric | Type | Labels | Meaning |
|---|---|---|---|
| `orderapi_http_requests_total` | Counter | `method`, `endpoint`, `status` | All HTTP requests |
| `orderapi_http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency in seconds |
| `orderapi_orders_created_total` | Counter | none | Business event: orders created |
| `orderapi_orders_failed_total` | Counter | `reason` | Failed orders (`invalid_input`, `internal_error`) |

Labels are bounded: `endpoint` uses the route pattern (not the raw URL), and `reason` has only two values.

### Quick test

```bash
curl -s localhost:8000/health
curl -s -X POST localhost:8000/api/orders -H 'Content-Type: application/json' -d '{"item":"book","quantity":2}'
curl -s -X POST "localhost:8000/api/orders?fail=true" -H 'Content-Type: application/json' -d '{"item":"book","quantity":1}'
curl -s -X POST localhost:8000/api/orders -H 'Content-Type: application/json' -d '{}'
curl -s localhost:8000/metrics | grep orderapi
```

---

## 9. Prometheus

<img width="1913" height="892" alt="Screenshot 2026-11-12 103110" src="https://github.com/user-attachments/assets/b508cd29-4dd2-41b9-aaab-11193e129e3c" />


`prometheus/prometheus.yml` defines two scrape jobs with a 15 s interval:

| Job | Target |
|---|---|
| `node` | Node Exporter on the VM (`host.docker.internal:9100`) |
| `orderapi` | `app:8000` |

Node Exporter runs with `network_mode: host`, `pid: host` and a read-only mount of `/` at `/host`, so it reads the real host values.

### PromQL used

| Purpose | Expression |
|---|---|
| CPU % | `100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)` |
| RAM % | `(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100` |
| Requests/s | `sum(rate(orderapi_http_requests_total[1m]))` |
| Error rate % | `100 * sum(rate(orderapi_http_requests_total{status=~"5.."}[1m])) / sum(rate(orderapi_http_requests_total[1m]))` |
| p95 latency (s) | `histogram_quantile(0.95, sum by (le) (rate(orderapi_http_request_duration_seconds_bucket[5m])))` |
| Disk % (`/`) | `100 * (1 - node_filesystem_avail_bytes{mountpoint="/",fstype!="tmpfs"} / node_filesystem_size_bytes{mountpoint="/",fstype!="tmpfs"})` |
| Uptime (s) | `node_time_seconds - node_boot_time_seconds` |

How to read them:
- **CPU %**: the idle counter shows how long the CPU did nothing. `rate` turns it into a per-second value, and 100 minus idle is how busy the CPU is.
- **RAM %**: used memory is total minus available, divided by total.
- **Error rate**: the share of requests with a 5xx status.
- **p95**: 95 % of requests were faster than this value, computed from the histogram buckets.

### Cross-checks against Linux commands

```bash
free -m          # compare with the RAM % query
df -h /          # compare with the disk % query
uptime -p        # compare with the uptime query
```

The values match closely; small differences come from the moment each value is read.

---

## 10. Grafana dashboard
<img width="1912" height="916" alt="Screenshot 2026-11-12 103158" src="https://github.com/user-attachments/assets/dfef12fc-4ef1-4fa5-8863-bc3e600dad26" />


Dashboard: **Observability / System & Application Observability**, with 9 panels:

1. CPU usage %
2. RAM usage %
3. Disk usage % (`/`)
4. Network throughput (receive/transmit)
5. Requests per second
6. Error rate % (5xx)
7. p95 request latency
8. Orders created / failed per minute (business events)
9. Host uptime

The JSON is stored in `grafana/dashboards/observability.json` and is generated by `scripts/make_dashboard.py`:

```bash
python3 scripts/make_dashboard.py
docker compose restart grafana
```

### Kubernetes logs in Grafana Explore

<img width="1917" height="922" alt="Screenshot 2026-11-12 103314" src="https://github.com/user-attachments/assets/21fa1c67-23c2-4b23-902a-7a382a87d365" />


Open **Explore**, choose the **Loki** data source, set the range to *Last 15 minutes* and run one query at a time:

```
{namespace="observability-demo"}
{namespace="observability-demo", container="log-generator"} |= "ERROR"
{pod=~"log-generator.*"} |= "INFO"
```

---

## 11. Email alerting

| Item | Value |
|---|---|
| Contact point | `email-alerts` (Email integration) |
| Notification policy | Default policy routes to `email-alerts` |
| Alert rule | `OrderAPI target down` (folder `Observability`, group `app-health`) |
| Query | `up{job="orderapi"}`, reduced to the last value |
| Threshold | Fires when the value is **below 1** |
| Evaluation | Every **1 minute**, pending period **1 minute** |
| No data / error | Treated as **Alerting** |
| Recipient | The designated test inbox |
| Operator action | Run `docker compose ps` and `docker compose logs app`, fix the cause, then `docker compose start app` |

SMTP credentials are passed to Grafana through environment variables (`GF_SMTP_*`, read from `.env`). They are not stored in any committed file.

Exported rule: `alerting/alert-rule.yaml`. Details: `alerting/configuration-notes.md`.

### Trigger the alert safely
<img width="1051" height="161" alt="Screenshot 2026-11-12 104541" src="https://github.com/user-attachments/assets/341651a5-073f-4de8-866e-dfe46e862866" />


```bash
docker compose stop app      # the target goes DOWN
# wait about 2 to 3 minutes: Normal -> Pending -> Firing, then an email arrives
docker compose start app     # the rule returns to Normal
```
<img width="1051" height="161" alt="Screenshot 2026-11-12 104541" src="https://github.com/user-attachments/assets/55178542-529f-4259-837f-2bf9b1de42a0" />

---

## 12. Demonstration script

1. **Normal request:** `./scripts/traffic-test.sh normal`. The request rate is about 1/s, the error rate is low, and the log-generator prints `INFO` lines.
2. **Higher traffic:** `./scripts/traffic-test.sh high`. The requests/s panel and p95 latency rise, and the created-orders counter climbs quickly.
3. **Controlled failure:** `./scripts/traffic-test.sh failure`. The error rate and failed-orders panels rise. In Grafana Explore, the Kubernetes `ERROR` lines are visible next to the metric change.
4. **Alert:** `docker compose stop app`, wait for the alert to fire, and see the email.

Before/after counter check:

```bash
curl -s localhost:8000/metrics | grep orderapi_orders_created_total   # before
./scripts/traffic-test.sh normal
curl -s localhost:8000/metrics | grep orderapi_orders_created_total   # after
```

---

## 13. Verification checklist

```bash
docker compose ps                              # 5 services Up
curl http://172.17.0.1:3100/ready              # ready
microk8s status --wait-ready
microk8s kubectl get nodes
microk8s kubectl get pods -A
microk8s kubectl logs -n observability-demo deploy/log-generator --tail=10
```

- [ ] Prometheus Targets: `node` and `orderapi` are both UP
- [ ] Five PromQL results and two Ubuntu cross-checks
- [ ] Dashboard with 9 live panels
- [ ] Kubernetes logs visible with `kubectl logs` **and** in Grafana Explore
- [ ] Alert rule reached Firing and the email was received
- [ ] Screenshots saved in `evidence/`

---

## 14. Evidence

Screenshots are stored in `evidence/`. Credentials and sensitive details are hidden.

| File | Shows |
|---|---|
| `compose-and-cluster.png` | Versions, `docker compose ps`, MicroK8s status, `kubectl get pods -A` |
| `prometheus-targets.png` | Both targets UP |
| `grafana-metrics.png` | The metrics dashboard |
| `kubernetes-logs.png` | `kubectl logs` and the matching Grafana Explore query |
| `email-alert.png` | The received alert email (subject and time) |

---

## 15. Cleanup

```bash
# Kubernetes
microk8s helm3 uninstall alloy -n alloy
microk8s kubectl delete namespace alloy observability-demo

# Docker Compose (keep data)
docker compose down

# Docker Compose (also delete stored data)
docker compose down -v
```

---

## 16. Limitations and improvements

- **Single node, no high availability.** Prometheus, Loki and Grafana each run as one container.
- **Loki uses local filesystem storage** with no retention tuning. For production, use object storage and set retention limits.
- **Static scrape targets.** Prometheus could use service discovery or the Kubernetes operator.
- **Email is the only notification channel.** Adding Slack or on-call routing would improve response, together with more alert rules (high error rate, high latency, disk almost full).
- **Metrics from Kubernetes itself** (kube-state-metrics, cAdvisor) are not collected. Only its logs are.
- **The host metrics describe the Vagrant VM**, not the physical laptop.

---

## 17. Security notes

- No credentials are in the repository. `.env` is ignored by Git, and `.env.example` has placeholders only.
- When creating a ZIP, exclude `.env` (see below).
- Observability ports are bound to `127.0.0.1` (Loki to the Docker bridge address only).

### Create the submission ZIP

```bash
cd ~
zip -r 30260_observability.zip 30260_observability -x "30260_observability/.env" "*/__pycache__/*"
```

---

## 18. Documentation used

- Docker Compose, MicroK8s, Kubernetes, Prometheus, Node Exporter
- Grafana Alloy (Kubernetes logs), Grafana Loki
- Grafana email contact points and SMTP configuration
