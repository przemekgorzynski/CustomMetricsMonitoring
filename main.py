from ping3 import ping
import time, json

def ping_func(hosts):
  inner_json_list = []
  outer_json_list = []
  result = {}
  for host in hosts:
    extime = int(time.time())
    result['host'] = host
    result['ping'] = ping(host,unit='s', timeout=10)
    result['time'] = extime
    inner_json_list.append(result)
    outer_json_list.append(inner_json_list)
  return outer_json_list

def write_to_json(data, filename):
    with open(filename, 'a') as file:
        json.dump(data, file)
        file.write('\n') 

hosts = ['1.1.1.1','8.8.8.8']
json_data = ping_func(hosts)
write_to_json(json_data, 'ping_results.json')
