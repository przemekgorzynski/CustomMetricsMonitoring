#!/usr/bin/env python3
import subprocess, psutil

def get_drives() -> list:
  drives = []
  for partition in psutil.disk_partitions(all=False):
    drives.append(partition.device)
    print(partition)
  return drives

drives = get_drives()

for drive in drives:
  print(drive)
  hdd = psutil.disk_usage("/")
  print("Total: %d GiB" % (hdd[0] / (1024 ** 3)))
  print("Used:  %d GiB" % (hdd[1] / (1024 ** 3)))
  print("Free:  %d GiB" % (hdd[2] / (1024 ** 3)))