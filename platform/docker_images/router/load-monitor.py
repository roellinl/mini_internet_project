#!/usr/bin/python3
import os
import time
import sys

timestep = 10
internal = 1
counter = 0
if len(sys.argv) == 2:
    timestep = float(sys.argv[1])

links = os.popen("ifconfig -a | sed 's/[ :\t].*//;/^$/d'").read().split()
config = f"conf t \n"
tx = dict()
rx = dict()
max_bw = dict()
tx_old = dict()
rx_old = dict()
link_use = dict()
time.sleep(10)

last_ts = time.time()

for link in links:
    if "port_" not in link:
        continue
    linkstring = os.popen(f'ip -s -s link show dev {link}').read()
    print(linkstring)
    rx_old[link] = float(linkstring.split("\n")[3].lstrip().split()[0])
    tx_old[link] = float(linkstring.split("\n")[7].lstrip().split()[0])
    for line in os.popen(f'echo -e "show interface {link}" | vtysh').read().split("\n"):
        if "Maximum Bandwidth" in line:
            max_bw[link] = float(line.lstrip().split()[2])
    link_use[link] = 0
    print(max_bw)
    print(f"{link}")
    print(f"receive bytes: {rx}")
    print(f"trasceive bytes: {tx}")
time.sleep(internal)

while True:
    counter += 1
    links = os.popen("ifconfig -a | sed 's/[ :\t].*//;/^$/d'").read().split()
    # print(links)
    config = f"conf t \n"
    timeframe = time.time()-last_ts
    last_ts = time.time()
    for link in links:
        if "port_" not in link:
            continue
        linkstring = os.popen(f'ip -s -s link show dev {link}').read().split("\n")
        if "UP" not in linkstring[0]:
            print(linkstring[0],flush=True)
            continue
        rx[link] = float(linkstring[3].lstrip().split()[0])
        tx[link] = float(linkstring[7].lstrip().split()[0])
        link_use[link] = round(link_use[link]*0.2 + 0.8*round(max(rx[link]-rx_old[link],tx[link]-tx_old[link])/timeframe))
        config += f"interface {link} \n link-params \n \
            ava-bw {max(0,max_bw[link]-link_use[link])} \n use-bw {link_use[link]} \n exit \n exit \n"
        rx_old[link], tx_old[link] = rx[link], tx[link]
    config+=f"exit \n exit \n"
    if counter == timestep:
        print(os.popen(f'echo -e "{config}" | vtysh').read())
        counter = 0
    time.sleep(internal)
    print(time.time())
