#!/usr/bin/env bash
# Usage: ./scripts/traffic-test.sh <normal|high|failure>
URL=${URL:-http://localhost:8000}
MODE=${1:-normal}
post() {
  curl -s -o /dev/null -w "%{http_code}\n" -X POST "$URL/api/orders$1" \
    -H 'Content-Type: application/json' -d '{"item":"book","quantity":1}'
}
case "$MODE" in
  normal)  for i in $(seq 1 30);  do post ""; sleep 1;    done ;;
  high)    for i in $(seq 1 600); do post "" & sleep 0.05; done; wait ;;
  failure) for i in $(seq 1 40);  do post "?fail=true"; sleep 0.5; done ;;
  *) echo "usage: $0 normal|high|failure"; exit 1 ;;
esac
