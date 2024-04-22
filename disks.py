#!/usr/bin/env python3

import psutil
types_monitor = ['sd', 'mmc', 'nvme']

def get_disk_info():
    disk_info = {}
    partitions = psutil.disk_partitions(all=False)
    for partition in partitions:
        for ptype in types_monitor:
          if ptype in partition.device:
            usage = psutil.disk_usage(partition.mountpoint)
            disk_info[partition.device] = {
                "mountpoint": partition.mountpoint,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent
            }
    return disk_info

print(get_disk_info())