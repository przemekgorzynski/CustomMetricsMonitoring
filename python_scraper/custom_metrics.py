#!/usr/bin/env python3
from prometheus_client import start_http_server, Gauge, Counter
import time, os, glob, json, re, subprocess, logging, psutil
from datetime import datetime
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
DISK_READS = Gauge('homelab_disk_reads_total', 'Read operations completed since boot', ['device'])
DISK_WRITES = Gauge('homelab_disk_writes_total', 'Write operations completed since boot', ['device'])
DISK_READ_TIME = Gauge('homelab_disk_read_time_seconds_total', 'Time spent serving reads since boot', ['device'])
DISK_WRITE_TIME = Gauge('homelab_disk_write_time_seconds_total', 'Time spent serving writes since boot', ['device'])
DISK_IO_TIME = Gauge('homelab_disk_io_time_seconds_total', 'Time with at least one request in flight since boot', ['device'])
NET_RECV = Gauge('homelab_network_receive_bytes_total', 'Bytes received since boot', ['device'])
NET_SENT = Gauge('homelab_network_transmit_bytes_total', 'Bytes sent since boot', ['device'])
NET_ERRORS = Gauge('homelab_network_errors_total', 'Network errors since boot', ['device', 'direction'])
MEMORY_TOTAL = Gauge('homelab_memory_total_bytes', 'Total memory')
MEMORY_USED = Gauge('homelab_memory_used_bytes', 'Memory used')
SWAP_USED = Gauge('homelab_swap_used_bytes', 'Swap used')
CPU_USAGE = Gauge('homelab_cpu_usage_percent', 'CPU usage across all cores')
LOAD_AVERAGE = Gauge('homelab_load_average', 'Load average', ['period'])
TEMPERATURE = Gauge('homelab_temperature_celsius', 'Sensor temperature', ['chip', 'sensor'])
BOOT_TIME = Gauge('homelab_boot_time_seconds', 'Unix time of last boot')
ZPOOL_SIZE = Gauge('homelab_zpool_size_bytes', 'Pool raw size', ['pool'])
ZPOOL_ALLOCATED = Gauge('homelab_zpool_allocated_bytes', 'Pool raw space allocated', ['pool'])
ZPOOL_FREE = Gauge('homelab_zpool_free_bytes', 'Pool raw space free', ['pool'])
ZPOOL_CAPACITY = Gauge('homelab_zpool_capacity_percent', 'Pool space used', ['pool'])
ZPOOL_FRAGMENTATION = Gauge('homelab_zpool_fragmentation_percent', 'Pool free space fragmentation', ['pool'])
ZPOOL_ONLINE = Gauge('homelab_zpool_online', 'Pool health is ONLINE', ['pool', 'health'])
ZPOOL_SCRUB_LAST_START = Gauge('homelab_zpool_scrub_last_start_seconds', 'Unix time the last scrub started', ['pool'])
ZPOOL_SCRUB_ERRORS = Gauge('homelab_zpool_scrub_errors', 'Errors found by the last finished scrub', ['pool'])
ZPOOL_SCRUB_RUNNING = Gauge('homelab_zpool_scrub_running', 'A scrub is currently running', ['pool'])
ZPOOL_VDEV_ONLINE = Gauge('homelab_zpool_vdev_online', 'Vdev state is ONLINE', ['pool', 'vdev', 'type', 'state'])
ZPOOL_VDEV_ERRORS = Gauge('homelab_zpool_vdev_errors', 'Errors on a vdev since the counters were last cleared', ['pool', 'vdev', 'type', 'error'])
ZPOOL_VDEV_CHILDREN = Gauge('homelab_zpool_vdev_children', 'Devices making up a redundant vdev', ['pool', 'vdev', 'type'])
ZPOOL_VDEV_CHILDREN_ONLINE = Gauge('homelab_zpool_vdev_children_online', 'Devices of a redundant vdev that are ONLINE', ['pool', 'vdev', 'type'])
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

# Partitions carry a partition file in sysfs, whole disks do not
def whole_disk(device:str) -> bool:
  return not os.path.exists(f'/sys/class/block/{device}/partition')

def disk_io_metrics():
  for device, io in psutil.disk_io_counters(perdisk=True).items():
    if not monitored('/dev/' + device) or not whole_disk(device):
      continue
    DISK_READ.labels(device).set(io.read_bytes)
    DISK_WRITE.labels(device).set(io.write_bytes)
    DISK_READS.labels(device).set(io.read_count)
    DISK_WRITES.labels(device).set(io.write_count)
    # Latency needs time and operation count as separate counters so that
    # Prometheus divides their rates; a ratio averaged here would be since boot.
    # psutil reports these in milliseconds, busy_time only on Linux
    DISK_READ_TIME.labels(device).set(io.read_time / 1000)
    DISK_WRITE_TIME.labels(device).set(io.write_time / 1000)
    DISK_IO_TIME.labels(device).set(getattr(io, 'busy_time', 0) / 1000)

# Physical interfaces link to their device in sysfs, veth and bridges do not
def physical_nic(device:str) -> bool:
  return os.path.exists(f'/sys/class/net/{device}/device')

def network_metrics():
  for device, io in psutil.net_io_counters(pernic=True).items():
    if not physical_nic(device):
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

def sysfs_read(path:str) -> str | None:
  try:
    with open(path) as handle:
      return handle.read().strip()
  except OSError:
    return None

# psutil groups hwmon chips by their name, so two chips sharing one name (a
# second NVMe drive) overwrite each other; sysfs keeps them apart
def temperature_metrics():
  for chip_path in sorted(glob.glob('/sys/class/hwmon/hwmon*')):
    name = sysfs_read(f'{chip_path}/name')
    if name is None:
      continue
    device = f'{chip_path}/device'
    chip = os.path.basename(os.path.realpath(device)) if os.path.exists(device) else name
    for input_path in sorted(glob.glob(f'{chip_path}/temp*_input')):
      reading = sysfs_read(input_path)
      if reading is None:
        continue
      sensor = sysfs_read(input_path.removesuffix('_input') + '_label')
      TEMPERATURE.labels(chip, sensor or name).set(int(reading) / 1000)

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

# zpool status reports only the most recent scan, so a resilver hides when the
# pool was last scrubbed; zpool history keeps every scrub and timestamps it
# without locale-formatted dates, which the status output uses
SCRUB_STARTED = re.compile(r'^(\d{4}-\d{2}-\d{2}\.\d{2}:\d{2}:\d{2}) zpool scrub (\S+)$')

def last_scrub_start(pool:str) -> float:
  output = subprocess.run(['zpool', 'history', pool], capture_output=True, text=True)
  if output.returncode:
    raise RuntimeError(output.stderr.strip() or f'zpool exited {output.returncode}')
  starts = []
  for line in output.stdout.splitlines():
    found = SCRUB_STARTED.match(line.strip())
    if found and found.group(2) == pool:
      starts.append(found.group(1))
  if not starts:
    return float('nan')
  # History is written in the host's local time; a container on a different
  # offset is hours out, which is noise against a threshold set in weeks
  return datetime.strptime(starts[-1], '%Y-%m-%d.%H:%M:%S').timestamp()

# A mirror only protects anything while every leg is ONLINE, and the counters
# below rise long before ZFS downgrades the pool, so they are the early warning
def vdev_metrics(pool:str, vdevs:dict):
  for name, vdev in (vdevs or {}).items():
    kind = vdev.get('vdev_type', '')
    children = vdev.get('vdevs') or {}
    if kind != 'root':
      ZPOOL_VDEV_ONLINE.labels(pool, name, kind, vdev.get('state', '')).set(1 if vdev.get('state') == 'ONLINE' else 0)
      for error in ('read', 'write', 'checksum'):
        ZPOOL_VDEV_ERRORS.labels(pool, name, kind, error).set(int(vdev.get(f'{error}_errors', 0)))
      if children:
        ZPOOL_VDEV_CHILDREN.labels(pool, name, kind).set(len(children))
        ZPOOL_VDEV_CHILDREN_ONLINE.labels(pool, name, kind).set(
          sum(1 for leg in children.values() if leg.get('state') == 'ONLINE')
        )
    vdev_metrics(pool, children)

def zpool_status_metrics():
  if not os.path.exists('/dev/zfs'):
    return
  output = subprocess.run(['zpool', 'status', '-j'], capture_output=True, text=True)
  if output.returncode:
    raise RuntimeError(output.stderr.strip() or f'zpool exited {output.returncode}')
  for pool, state in json.loads(output.stdout).get('pools', {}).items():
    scan = state.get('scan_stats') or {}
    scrubbing = scan.get('function') == 'SCRUB'
    ZPOOL_SCRUB_RUNNING.labels(pool).set(1 if scrubbing and scan.get('state') == 'SCANNING' else 0)
    finished = scrubbing and scan.get('state') == 'FINISHED'
    ZPOOL_SCRUB_ERRORS.labels(pool).set(int(scan['errors']) if finished else float('nan'))
    ZPOOL_SCRUB_LAST_START.labels(pool).set(last_scrub_start(pool))
    vdev_metrics(pool, state.get('vdevs'))

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
  'zpool_status': zpool_status_metrics,
  'uptime': uptime_metrics,
}

# A counter child is only created once it is incremented, so a healthy run
# exports nothing and the panel cannot be told apart from a dead exporter
for name in collectors:
  SCRAPE_ERRORS.labels(name)

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
