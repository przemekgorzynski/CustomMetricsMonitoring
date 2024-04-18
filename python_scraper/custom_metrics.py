#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge
import time, os, logging
from ping3 import ping

# Logging definition
logging.basicConfig(
  level=logging.INFO, format="%(levelname)s | %(asctime)s | %(message)s",
  datefmt='%Y-%m-%d %H:%M:%S',
)

# Define Prometheus gauge metric
PING_VALUE = Gauge('ping_rsponse_time', 'Time of ping', ['target'])

# Ping Targets
hosts = (os.environ['PING_TARGETS']).split(',')

def ping_function(target:str) -> float:
  ping_time = ping(target, unit='s', timeout=10)
  return ping_time

if __name__ == '__main__':
  # Start Prometheus HTTP server on port 8000
  start_http_server(8000)

  logging.info('======== Serving metrics at :8000; Metric are collected every 5s ========')

  while True:
    try:
      for target in hosts:
        ping_time = ping_function(target)
        PING_VALUE.labels(target).set(ping_time)
        logging.info('Sucessfull ping %s', target)
      time.sleep(5)
    except:
      logging.info('Unsucessfull ping %s', target)
      time.sleep(5) 