#!/usr/bin/python3
import os
import time
import sys
import socket
from multiprocessing import Process

topology = "mini-internet"

if topology == "mini-internet":
    controller_ip = "1.157.0.1"
    translate = {"1.151.0.1": "ZURI", "1.152.0.1": "BASE", "1.153.0.1": "GENE", "1.154.0.1": "LUGA", "1.155.0.1": "MUNI", "1.156.0.1": "LYON", "1.157.0.1": "VIEN", "1.158.0.1": "MILA"}
elif topology == "eth":
    controller_ip = "1.153.0.1"
    translate = {'1.151.0.1': 'BGW-LEE', '1.152.0.1': 'FW-LEE', '1.153.0.1': 'GW-LEE', '1.154.0.1': 'GW-HCI', '1.155.0.1': 'FW-HCI', '1.156.0.1': 'BGW-HCI', '1.157.0.1': 'OCT', '1.158.0.1': 'OX', '1.159.0.1': 'BS', '1.160.0.1': 'SB-LEE', '1.161.0.1': 'SB-HCI', '1.162.0.1': 'REF-LEE', '1.163.0.1': 'REF-HG', '1.164.0.1': 'REF-HCI', '1.165.0.1': 'REF-HPP'}

nodes = list(translate.keys())


def send_command(ip, port, command):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    s.sendall(command.encode())
    s.close()


def wake_up_network():
    print("wake all")
    print(f"time of congestion: {time.time()}")
    for node in nodes:
        Process(target=send_command, args=(node, 2023, "wake all")).start()
    Process(target=send_command, args=(controller_ip, 2024, "wake all")).start()
    return


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
time.sleep(20)

last_ts = time.time()

for link in links:
    if "port_" not in link:
        continue
    linkstring = os.popen(f'ip -s -s link show dev {link}').read()
    #print(linkstring)
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
    start = time.time()
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
        
        rx[link] = float(linkstring[3].lstrip().split()[0])
        tx[link] = float(linkstring[7].lstrip().split()[0])
        link_use[link] = min(max_bw[link],round(link_use[link]*0.1 + 0.9*round((tx[link]-tx_old[link])/timeframe)))

        if link_use[link]/max_bw[link] > 0.8:
            print(f"utilization: {link_use[link]/max_bw[link]}")
            print(f"link {link} is congested")
            wake_up_network()

        rx_old[link], tx_old[link] = rx[link], tx[link]
        if "UP" not in linkstring[0]:
            print(f"One of the Ports is down: {linkstring[0]}",flush=True)
        config += f"interface {link} \n link-params \n \
            ava-bw {max(0,max_bw[link]-link_use[link])} \n use-bw {link_use[link]} \n exit \n exit \n"
    config+=f"exit \n exit \n"
    if counter == timestep:
        os.popen(f'echo -e "{config}" | vtysh').read()
        counter = 0
    end = time.time()
    if (end - start) > internal:
        print(f"Warning: timestep took {end - start} seconds")
    time.sleep(max(0, 1 - (end - start)))
    #print(time.time())
