#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge
import time, os, logging, psutil
from ping3 import ping

# Uptime
def uptime():
  return time.time() - psutil.boot_time()

print(uptime())