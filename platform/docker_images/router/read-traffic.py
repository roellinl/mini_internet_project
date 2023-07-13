import os
import networkx as nx
import time
import socket

sleep_edge = ["1.151.0.1","1.154.0.1"]

for router in sleep_edge:
    print(router)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((router, 2023))
    s.sendall(f"wake all".encode())
    s.close()

sleep = False
wakeup_counter = 0

def read_traffic():
    ospf = os.popen(f'echo -e "show ip ospf database opaque-area" | vtysh').read()
    #print(ospf)
    ospf = ospf.split("LS age")[1:]
    elements = [None] * len(ospf)

    global sleep, wakeup_counter
    for link_no, link in enumerate(ospf):
        for index, line in enumerate(link.split("\n")):
            if "Router-Address" in line:
                elements[link_no] = {}
                elements[link_no]["router_ip"] = line.split(":")[1].strip()
            if "Link-Type" in line:
                elements[link_no]["link_type"] = line.split(":")[1].strip()
            if "Link-ID" in line:
                elements[link_no]["link_id"] = line.split(":")[1].strip()
            if "Local Interface IP Address" in line:
                elements[link_no]["link_ip"] = link.split("\n")[index+1].split(":")[1].lstrip()
            if "Remote Interface IP Address" in line:
                elements[link_no]["remote_ip"] = link.split("\n")[index+1].split(":")[1].lstrip()
            if "Available Bandwidth" in line:
                elements[link_no]["avail"] = float(line.split(":")[1].strip().split()[0])
            if "Utilized Bandwidth" in line:
                elements[link_no]["usage"] = float(line.split(":")[1].strip().split()[0])
            if "Maximum Bandwidth" in line:
                elements[link_no]["bw"] = float(line.split(":")[1].strip().split()[0])
    #print(elements)
    nodes = set([i["router_ip"] for i in elements])
    G = nx.Graph()
    G.add_nodes_from(nodes)
    link_ids = set()
    edges = []
    for index, link in enumerate(elements):
        if "Multiaccess" in link["link_type"]:
            for link2 in elements[index+1:]:
                if link["link_id"] == link2["link_id"]:
                    if link["link_id"] in link_ids:
                        break
                    edges.append((link["router_ip"], link2["router_ip"], 
                        {"ip": {f"{link['router_ip']}": link["link_ip"], f"{link2['router_ip']}": link2["link_ip"]},
                            "avail": max(0, min(link['avail'], link2['avail'])),
                            "usage": max(link['usage'], link2['usage']),
                            "max_bw": max(link['bw'], link2['bw'])}))
                    link_ids.add(link["link_id"])
        if "Point-to-point" in link["link_type"]:
            for link2 in elements[index+1:]:
                if link["remote_ip"] == link2["link_ip"]:
                    if link["link_ip"] in link_ids:
                        break
                    edges.append((link["router_ip"], link2["router_ip"], 
                        {"ip": {f"{link['router_ip']}": link["link_ip"], f"{link2['router_ip']}": link2["link_ip"]},
                            "avail": max(0, min(link['avail'], link2['avail'])),
                            "usage": max(link['usage'], link2['usage']),
                            "max_bw": max(link['bw'], link2['bw'])}))
                    link_ids.add(link["remote_ip"])

        
    G.add_edges_from(edges)
    #print(edges)
    avail = [G[i[0]][i[1]]["avail"] for i in nx.edges(G)]
    bws = [i["bw"] for i in elements]
    
    minimum = min(avail)

    for edge in nx.edges(G):
        if sleep_edge[0] in edge and sleep_edge[1] in edge:
            sleep_edge_bw = G[edge[0]][edge[1]]
            print("Monitored Edge: ")
            print(G[edge[0]][edge[1]])
            continue
        #print(edge)
        print(G[edge[0]][edge[1]])
    
    wakeup_counter -= 1
    for i, link in enumerate(avail):
        if link/bws[i] < 0.2:
            print(f" utilization {link/bws[i]} {elements[i]['link_id']}")
            print("wake up")
            wakeup_counter = 10
            if not sleep:
                print("already awake")
                return
            for router in sleep_edge:
                print(router)
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((router, 2023))
                s.sendall(f"wake {sleep_edge_bw['ip'][router]}".encode())
                s.close()
            sleep = False
            return

    if sleep_edge_bw["usage"] < minimum:
        print("set to sleep")
        if wakeup_counter > 0:
            print("wakeup in progress")
            return
        if sleep:
            print("already set to sleep")
            return
        for router in sleep_edge:
            print(router)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"sleep {sleep_edge_bw['ip'][router]}".encode())
            s.close()
        sleep = True
        return

for i in range(120):
    read_traffic()
    print("\n",flush=True)
    time.sleep(1)


for router in sleep_edge:
    print(router)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((router, 2023))
    s.sendall(f"wake all".encode())
    s.close()

sleep = False

