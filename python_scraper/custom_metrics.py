#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge, Counter
import time, os, subprocess, logging, psutil
from ping3 import ping

# Logging definition
logging.basicConfig(
  level=logging.INFO, format="%(levelname)s | %(asctime)s | %(message)s",
  datefmt='%Y-%m-%d %H:%M:%S',
)

# Define Prometheus metrics
PING_TIME = Gauge('homelab_ping_response_time_seconds', 'Ping round trip time', ['target'])
PING_UP = Gauge('homelab_ping_up', 'Ping reachable (1) or not (0)', ['target'])
DISK_SIZE = Gauge('homelab_disk_size_bytes', 'Disk size', ['device'])
DISK_USED = Gauge('homelab_disk_used_bytes', 'Disk space used', ['device'])
DISK_INODES = Gauge('homelab_disk_inodes', 'Inodes on the filesystem', ['device'])
DISK_INODES_USED = Gauge('homelab_disk_inodes_used', 'Inodes used', ['device'])
DISK_READ = Gauge('homelab_disk_read_bytes_total', 'Bytes read since boot', ['device'])
DISK_WRITE = Gauge('homelab_disk_write_bytes_total', 'Bytes written since boot', ['device'])
NET_RECV = Gauge('homelab_network_receive_bytes_total', 'Bytes received since boot', ['device'])
NET_SENT = Gauge('homelab_network_transmit_bytes_total', 'Bytes sent since boot', ['device'])
NET_ERRORS = Gauge('homelab_network_errors_total', 'Network errors since boot', ['device', 'direction'])
MEMORY_TOTAL = Gauge('homelab_memory_total_bytes', 'Total memory')
MEMORY_USED = Gauge('homelab_memory_used_bytes', 'Memory used')
SWAP_USED = Gauge('homelab_swap_used_bytes', 'Swap used')
CPU_USAGE = Gauge('homelab_cpu_usage_percent', 'CPU usage across all cores')
LOAD_AVERAGE = Gauge('homelab_load_average', 'Load average', ['period'])
TEMPERATURE = Gauge('homelab_temperature_celsius', 'Sensor temperature', ['sensor'])
BOOT_TIME = Gauge('homelab_boot_time_seconds', 'Unix time of last boot')
ZPOOL_SIZE = Gauge('homelab_zpool_size_bytes', 'Pool raw size', ['pool'])
ZPOOL_ALLOCATED = Gauge('homelab_zpool_allocated_bytes', 'Pool raw space allocated', ['pool'])
ZPOOL_FREE = Gauge('homelab_zpool_free_bytes', 'Pool raw space free', ['pool'])
ZPOOL_CAPACITY = Gauge('homelab_zpool_capacity_percent', 'Pool space used', ['pool'])
ZPOOL_FRAGMENTATION = Gauge('homelab_zpool_fragmentation_percent', 'Pool free space fragmentation', ['pool'])
ZPOOL_ONLINE = Gauge('homelab_zpool_online', 'Pool health is ONLINE', ['pool', 'health'])
SCRAPE_ERRORS = Counter('homelab_scrape_errors_total', 'Failed collections', ['collector'])

# Ping Targets
hosts = (os.environ['PING_TARGETS']).split(',')

def ping_metrics():
  for target in hosts:
    ping_time = ping(target, unit='s', timeout=10)
    if isinstance(ping_time, float):
      PING_TIME.labels(target).set(ping_time)
      PING_UP.labels(target).set(1)
    else:
      PING_TIME.labels(target).set(float('nan'))
      PING_UP.labels(target).set(0)

# Disk metrics. HOST_FS_PREFIX points at the host root when running in a container
types_monitor = (os.environ['DISK_TYPES_TO_MONITOR']).split(',')
disk_devices = (os.environ.get('DISK_DEVICES', '')).split(',')
host_fs = os.environ.get('HOST_FS_PREFIX', '')

# Block devices match on type substring, pools (zfs, btrfs) on their exact name
def monitored(device:str) -> bool:
  if device.startswith('/dev/'):
    return any(ptype in device for ptype in types_monitor)
  return device in disk_devices

def disk_metrics():
  for partition in psutil.disk_partitions(all=False):
    if not monitored(partition.device):
      continue
    usage = psutil.disk_usage(host_fs + partition.mountpoint)
    stat = os.statvfs(host_fs + partition.mountpoint)
    DISK_SIZE.labels(partition.device).set(usage.total)
    DISK_USED.labels(partition.device).set(usage.used)
    DISK_INODES.labels(partition.device).set(stat.f_files)
    DISK_INODES_USED.labels(partition.device).set(stat.f_files - stat.f_ffree)

def disk_io_metrics():
  for device, io in psutil.disk_io_counters(perdisk=True).items():
    if not monitored('/dev/' + device):
      continue
    DISK_READ.labels(device).set(io.read_bytes)
    DISK_WRITE.labels(device).set(io.write_bytes)

def network_metrics():
  for device, io in psutil.net_io_counters(pernic=True).items():
    if device == 'lo':
      continue
    NET_RECV.labels(device).set(io.bytes_recv)
    NET_SENT.labels(device).set(io.bytes_sent)
    NET_ERRORS.labels(device, 'receive').set(io.errin + io.dropin)
    NET_ERRORS.labels(device, 'transmit').set(io.errout + io.dropout)

def memory_metrics():
  MEMORY_TOTAL.set(psutil.virtual_memory().total)
  MEMORY_USED.set(psutil.virtual_memory().used)
  SWAP_USED.set(psutil.swap_memory().used)

def cpu_metrics():
  CPU_USAGE.set(psutil.cpu_percent())
  for period, value in zip(['1m', '5m', '15m'], psutil.getloadavg()):
    LOAD_AVERAGE.labels(period).set(value)

def temperature_metrics():
  # Linux only, psutil does not expose sensors elsewhere
  sensors = getattr(psutil, 'sensors_temperatures', dict)()
  for name, entries in sensors.items():
    for entry in entries:
      TEMPERATURE.labels(entry.label or name).set(entry.current)

# Pool capacity is raw, matching zpool list, so it does not equal the usable
# space that statvfs reports for the datasets
def zpool_metrics():
  if not os.path.exists('/dev/zfs'):
    return
  fields = 'name,size,alloc,free,cap,frag,health'
  output = subprocess.run(['zpool', 'list', '-Hp', '-o', fields], capture_output=True, text=True)
  if output.returncode:
    raise RuntimeError(output.stderr.strip() or f'zpool exited {output.returncode}')
  for line in output.stdout.splitlines():
    pool, size, alloc, free, cap, frag, health = line.split('\t')
    ZPOOL_SIZE.labels(pool).set(int(size))
    ZPOOL_ALLOCATED.labels(pool).set(int(alloc))
    ZPOOL_FREE.labels(pool).set(int(free))
    ZPOOL_CAPACITY.labels(pool).set(int(cap))
    ZPOOL_FRAGMENTATION.labels(pool).set(int(frag) if frag.isdigit() else float('nan'))
    ZPOOL_ONLINE.labels(pool, health).set(1 if health == 'ONLINE' else 0)

def uptime_metrics():
  BOOT_TIME.set(psutil.boot_time())

collectors = {
  'ping': ping_metrics,
  'disk': disk_metrics,
  'disk_io': disk_io_metrics,
  'network': network_metrics,
  'memory': memory_metrics,
  'cpu': cpu_metrics,
  'temperature': temperature_metrics,
  'zpool': zpool_metrics,
  'uptime': uptime_metrics,
}

if __name__ == '__main__':
  # Start Prometheus HTTP server on port 8000
  start_http_server(8000)
  logging.info('======== Serving metrics at :8000; Metric are collected every 20s ========')

  while True:
    time.sleep(20)
    for name, collector in collectors.items():
      try:
        collector()
        logging.info('Collected %s', name)
      except Exception as error:
        SCRAPE_ERRORS.labels(name).inc()
        logging.warning('Failed to collect %s: %s', name, error)
