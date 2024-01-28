import os

with os.popen('ip neigh show') as result:
    # permanent, noarp, reachable, stale, none, incomplete, delay, probe, failed
    ip = '192.168.10.56'
    mac = "b4:b5:2f:ce:6d:29"
    value = False
    lines = str(result.read()).splitlines()
    for line in lines:
        if (ip in line or mac in line) and ("REACHABLE" in line or "STALE" in line):
            value = True
            break
    #sh.devices.laptop.status(value)​
    print(f"set item to {value}")