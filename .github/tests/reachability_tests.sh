#!/bin/bash
set -e

RESPONSE_BOTTOM_LIMIT=200
RESPONSE_UPPER_LIMIT=400

METRICS_URL=http://127.0.0.1:8000/
PROMETHEUS_URL=http://127.0.0.1:9090/graph
GRAFANA_URL=http://127.0.0.1:3000/login

check_page(){
  if (( $(curl  -o /dev/null -s -w "%{http_code}\n" $1) >= "$RESPONSE_BOTTOM_LIMIT" && $(curl  -o /dev/null -s -w "%{http_code}\n" $1) <= "$RESPONSE_UPPER_LIMIT" ))
  then
    echo "Response: "$(curl  -o /dev/null -s -w "%{http_code}\n" $1)" from $2 page $1"
  else
    echo "Response: "$(curl  -o /dev/null -s -w "%{http_code}\n" $1)" from $2 page $1"
    echo "FAILING..."
    echo "================================================================="
    exit 1
  fi
}


echo "***** PAGE HTTP RESPONSE SHOULD BE IN RANGE $RESPONSE_BOTTOM_LIMIT-$RESPONSE_UPPER_LIMIT *****"
echo "================================================================="
check_page $METRICS_URL "Metrics"
check_page $GRAFANA_URL "Grafana"
check_page $PROMETHEUS_URL "Prometheus"
echo "================================================================="
echo "***** REACHABILITY TESTS PASSED *****"