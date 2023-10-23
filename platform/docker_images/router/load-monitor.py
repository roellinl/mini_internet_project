#!/usr/bin/python3
import os
import time
import sys
import socket
from multiprocessing import Process
import struct
from scapy.all import Ether, IP, sendp, wrpcap, conf, send
from scapy.contrib.ospf import OSPF_Hdr, OSPF_LSUpd, OSPF_Area_Scope_Opaque_LSA, LLS_Generic_TLV
from ipaddress import IPv4Address
from multiprocessing import Process, Queue
seq = 2147483649

topology = "mini-internet"
timestep = 10
internal = 1
counter = 0
hysteresis = 5
hyst_counter = 0
type = "scapy"
linkmargin = 0.2
if len(sys.argv) >= 2:
    timestep = float(sys.argv[1])
if len(sys.argv) >= 3:
    delay = float(sys.argv[2])
if len(sys.argv) >= 4:
    type = sys.argv[3]
if len(sys.argv) >= 5:
    hysteresis = int(sys.argv[4])
if len(sys.argv) >= 6:
    linkmargin = float(sys.argv[5])
if len(sys.argv) >= 7:
    topology = sys.argv[6]

if topology == "mini-internet":
    controller_ip = "1.157.0.1"
    translate = {"1.151.0.1": "ZURI", "1.152.0.1": "BASE", "1.153.0.1": "GENE", "1.154.0.1": "LUGA", "1.155.0.1": "MUNI", "1.156.0.1": "LYON", "1.157.0.1": "VIEN", "1.158.0.1": "MILA"}
elif topology == "eth":
    controller_ip = "1.153.0.1"
    translate = {'1.151.0.1': 'BGW-LEE', '1.152.0.1': 'FW-LEE', '1.153.0.1': 'GW-LEE', '1.154.0.1': 'GW-HCI', '1.155.0.1': 'FW-HCI', '1.156.0.1': 'BGW-HCI', '1.157.0.1': 'OCT', '1.158.0.1': 'OX', '1.159.0.1': 'BS', '1.160.0.1': 'SB-LEE', '1.161.0.1': 'SB-HCI', '1.162.0.1': 'REF-LEE', '1.163.0.1': 'REF-HG', '1.164.0.1': 'REF-HCI', '1.165.0.1': 'REF-HPP'}
elif topology == "geant":
    controller_ip = "1.162.0.1"
    translate = {'1.151.0.1': 'SIN', '1.152.0.1': 'LIS', '1.153.0.1': 'POR', '1.154.0.1': 'BIL', '1.155.0.1': 'MAD', '1.156.0.1': 'PAR', '1.157.0.1': 'LON', '1.158.0.1': 'BRU', '1.159.0.1': 'AMS', '1.160.0.1': 'MAR', '1.161.0.1': 'GEN', '1.162.0.1': 'FRA', '1.163.0.1': 'HAM', '1.164.0.1': 'BER', '1.165.0.1': 'POZ', '1.166.0.1': 'PRA', '1.167.0.1': 'VIE', '1.168.0.1': 'MIL', '1.169.0.1': 'LJU', '1.170.0.1': 'ZAG', '1.171.0.1': 'BEL', '1.172.0.1': 'BRA', '1.173.0.1': 'BUD', '1.174.0.1': 'SOF', '1.175.0.1': 'BUC', '1.176.0.1': 'THE', '1.177.0.1': 'LUX', '1.178.0.1': 'ATH', '1.179.0.1': 'COR', '1.180.0.1': 'DUB', '1.181.0.1': 'COP', '1.182.0.1': 'HEL', '1.183.0.1': 'TAR', '1.184.0.1': 'RIG', '1.185.0.1': 'KAU'}
elif topology == "geant-full":
    controller_ip = "1.162.0.1"
    translate = {'1.151.0.1': 'SIN', '1.152.0.1': 'LIS', '1.153.0.1': 'POR', '1.154.0.1': 'BIL', '1.155.0.1': 'MAD', '1.156.0.1': 'PAR', '1.157.0.1': 'LON', '1.158.0.1': 'BRU', '1.159.0.1': 'AMS', '1.160.0.1': 'MAR', '1.161.0.1': 'GEN', '1.162.0.1': 'FRA', '1.163.0.1': 'HAM', '1.164.0.1': 'BER', '1.165.0.1': 'POZ', '1.166.0.1': 'PRA', '1.167.0.1': 'VIE', '1.168.0.1': 'MIL', '1.169.0.1': 'LJU', '1.170.0.1': 'ZAG', '1.171.0.1': 'BEL', '1.172.0.1': 'BRA', '1.173.0.1': 'BUD', '1.174.0.1': 'SOF', '1.175.0.1': 'BUC', '1.176.0.1': 'THE', '1.177.0.1': 'LUX', '1.178.0.1': 'VAL', '1.179.0.1': 'POD', '1.180.0.1': 'TIR', '1.181.0.1': 'SKO', '1.182.0.1': 'IST', '1.183.0.1': 'ATH', '1.184.0.1': 'NIC', '1.185.0.1': 'TEL', '1.186.0.1': 'COR', '1.187.0.1': 'DUB', '1.188.0.1': 'REY', '1.189.0.1': 'COP', '1.190.0.1': 'OSL', '1.191.0.1': 'STO', '1.192.0.1': 'HEL', '1.193.0.1': 'TAR', '1.194.0.1': 'RIG', '1.195.0.1': 'KAU', '1.196.0.1': 'KIE', '1.197.0.1': 'CHI'}
nodes = list(translate.keys())

print(f"parameters: timestep: {timestep}, delay: {delay}, type: {type}, hysteresis: {hysteresis}")

# sends command to node
def send_command(ip, port, command):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((ip, port))
    print(f"send command {command} to {ip}")
    s.sendall(command.encode())
    s.close()


# wakes up all nodes and informs controller
def wake_up_network():
    global delay
    print("wake all")
    print(f"time of congestion: {time.time()}")
    for node in nodes:
        Process(target=send_command, args=(node, 2023, f"wake all {delay}")).start()
    Process(target=send_command, args=(controller_ip, 2024, "wake all")).start()
    return


def create_te_metric(adv_r,local_ip,neigh_r,remote_ip,id,bandwidth,max_bandwidth,seq):
    router = LLS_Generic_TLV(type=1,len=4,val=adv_r.packed).build()
    link_val=1
    link_type_tlv = LLS_Generic_TLV(type=1,len=1,val=link_val.to_bytes(1,byteorder='big')).build()
    link_id_tlv = LLS_Generic_TLV(type=2,len=4,val=neigh_r.packed).build()
    local_ip_tlv = LLS_Generic_TLV(type=3,len=4,val=local_ip.packed).build()
    remote_ip_tlv = LLS_Generic_TLV(type=4,len=4,val=remote_ip.packed).build()
    max_bw_tlv = LLS_Generic_TLV(type=6,len=4,val=bytearray(struct.pack("!f", float(max_bandwidth)))).build()
    avail_tlv = LLS_Generic_TLV(type=33,len=4,val=bytearray(struct.pack("!f", float(bandwidth)))).build()
    

    link_data = link_type_tlv + b"\x00\x00\x00" + link_id_tlv + local_ip_tlv + remote_ip_tlv + avail_tlv  + max_bw_tlv

    link = LLS_Generic_TLV(type=2,val=link_data).build()

    data = router + link
    lsa = OSPF_Area_Scope_Opaque_LSA(id=id,adrouter=adv_r,age=1,options=0x42,seq=seq,data=data)

    return (lsa, adv_r)


def create_packet(link, bw, max_bw):
    global seq
    adv_r = IPv4Address(link[0][0])
    local_ip = IPv4Address(link[1][0])
    neigh_r= IPv4Address(link[0][1])
    remote_ip = IPv4Address(link[1][1])
    id_no = link[1][0].split(".")[2]
    id = f"1.0.0.{id_no}"
    seq += 1
    lsa = create_te_metric(adv_r,local_ip,neigh_r,remote_ip,id,int(bw),int(max_bw),seq)
    return lsa

def send_update(packet, iface):
    send(packet, iface=iface)

def send_ospf(port_dict, packets):
    for iface in port_dict.keys():
        dst_ip = port_dict[iface][1][1]
        print(dst_ip)
        lsa_list = []
        adv_r = packets[0][1]
        for packet in packets:
            lsa_list.append(packet[0])
        packet = OSPF_Hdr(type=4,src=adv_r)/OSPF_LSUpd(lsacount=len(lsa_list), lsalist=lsa_list)
        complete_packet = IP(src=str(port_dict[iface][1][0]), dst=str(dst_ip), tos=192)/packet[0]
        Process(target=send_update, args=(complete_packet,iface)).start()
    return


def read_network():
    ip_to_intf = {}
    link_ip = os.popen(f'echo -e "show interface brief \n exit \n" | vtysh').read()
    for interface in link_ip.split("\n")[7:-3]:
        if len(interface.split()) < 4:
            continue
        if "port_" in interface.split()[0]:
            linkid = interface.split()[3].split("/")[0]
            ip_to_intf[linkid] = interface.split()[0]
    print(ip_to_intf,flush=True)
    id_string = os.popen(f'echo -e "show ip ospf" | vtysh').read().split("\n")
    for line in id_string:
        if "OSPF Routing Process, Router ID" in line:
            id = line.split(":")[1].strip()
    nodes = os.popen(f'echo -e "show ip ospf database router" | vtysh').read().split("LS age:")
    router_intf = {}
    for node in nodes[1:]:
        router_id = node.split("\n")[5].split(":")[1].strip()
        router_intf[router_id] = []
        for links in node.split("Link connected to")[1:]:
            if "another Router" in links:
                lines = links.split("\n")
                router_intf[router_id].append((lines[1].split(":")[1].lstrip(),lines[2].split(":")[1].lstrip()))
    links_dict = {}
    
    for link in router_intf[id]:
        for element in router_intf[link[0]]:
            if element[0] == id:
                other_ip = element[1]
        links_dict[(id,link[0])] = (link[1],other_ip)
    port_dict = {}
    for router, link_ip in links_dict.items():
        port_name = ip_to_intf[link_ip[0]]
        port_dict[port_name] = (router, links_dict[router])
    print(port_dict,flush=True)
    return port_dict


def update_ospf(link_use, max_bw, ports_dict):
    packets = []
    for intf, usage in link_use.items():

        packets.append(create_packet(ports_dict[intf], usage, max_bw[intf]))
    send_ospf(ports_dict, packets)


def main():
    global counter, hyst_counter, hysteresis
    ports_dict = read_network()
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
            link_use[link] = min(max_bw[link],round(link_use[link]*0.2 + 0.8*round((tx[link]-tx_old[link])/timeframe)))

            if link_use[link]/max_bw[link] > (1-linkmargin):
                print(f"utilization: {link_use[link]/max_bw[link]}")
                print(f"link {link} is congested {time.time()}")
                if hyst_counter == 0:
                    wake_up_network()
                    hyst_counter = hysteresis

            rx_old[link], tx_old[link] = rx[link], tx[link]
            if "UP" not in linkstring[0]:
                print(f"One of the Ports is down: {linkstring[0]}",flush=True)

            config += f"interface {link} \n link-params \n use-bw {link_use[link]} \n exit \n exit \n"
        config+=f"exit \n exit \n"
        print(config)
        if counter == timestep:
            if type == "frr":
                os.popen(f'echo -e "{config}" | vtysh').read()
            elif type == "scapy":
                update_ospf(link_use, max_bw,ports_dict)
            counter = 0
        
        end = time.time()
        if hyst_counter > 0:
            hyst_counter -= 1
        if (end - start) > internal:
            print(f"Warning: timestep took {end - start} seconds")
        time.sleep(max(0, 1 - (end - start)))


if __name__ == "__main__":
    
    main()

