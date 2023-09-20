import os
import networkx as nx
import time
import socket
import argparse
from multiprocessing import Process


# Parse the arguments and set variables for the controller

start_proc = time.time()
timestep = 0

argparse = argparse.ArgumentParser()
argparse.add_argument("--topo", default="mini-internet", help="topology to use")
argparse.add_argument("--mode", default="smart", help="controller mode")
argparse.add_argument("--sleeptype", default="sleep", help="sleep type")
argparse.add_argument("--no_edges", default="all", help="number of sleep edges")
argparse.add_argument("--hyst", type=int, default=0 , help="hysterisis time")
argparse.add_argument("--linkmargin", type=float, default=0.2, help="link margin")
argparse.add_argument("--interval", type=int, default=1, help="controller interval")
argparse.add_argument("--wait_time", type=int, default=5, help="wait time before controller starts")
argparse.add_argument("--wake_delay", type=int, default=10, help="delay before link is actually ready")
argparse.add_argument("--wake_mode", default="dist", help="wake up signaling mode")
argparse.add_argument("--dist_hyst", type=int, default=10, help="hysterisis when controller gets distributed wake all signal")
argparse.add_argument("--max_util", type=float, default=0.4, help="maximum utilization to shut down a link")

args = argparse.parse_args()

print(args)

if args.topo == "mini-internet":
    sleep_edges = [("1.151.0.1","1.154.0.1"), ("1.151.0.1","1.153.0.1"), ("1.151.0.1","1.152.0.1"), ("1.151.0.1","1.157.0.1"), ("1.151.0.1","1.155.0.1"), ("1.153.0.1","1.152.0.1"), ("1.152.0.1","1.155.0.1"), ("1.153.0.1","1.156.0.1"), ("1.154.0.1","1.158.0.1"), ("1.152.0.1","1.156.0.1"), ("1.154.0.1","1.157.0.1"), ("1.153.0.1","1.154.0.1")]
    translate = {"1.151.0.1": "ZURI", "1.152.0.1": "BASE", "1.153.0.1": "GENE", "1.154.0.1": "LUGA", "1.155.0.1": "MUNI", "1.156.0.1": "LYON", "1.157.0.1": "VIEN", "1.158.0.1": "MILA"}
        
elif args.topo == "eth":
    sleep_edges = [('1.151.0.1', '1.152.0.1'), ('1.153.0.1', '1.152.0.1'), ('1.153.0.1', '1.154.0.1'), ('1.162.0.1', '1.152.0.1'), ('1.154.0.1', '1.155.0.1'), ('1.155.0.1', '1.152.0.1'), ('1.155.0.1', '1.164.0.1'), ('1.162.0.1', '1.164.0.1'), ('1.155.0.1', '1.156.0.1'), ('1.163.0.1', '1.160.0.1'), ('1.160.0.1', '1.162.0.1'), ('1.163.0.1', '1.162.0.1'), ('1.163.0.1', '1.165.0.1'), ('1.164.0.1', '1.161.0.1'), ('1.165.0.1', '1.161.0.1'), ('1.165.0.1', '1.164.0.1'), ('1.160.0.1', '1.161.0.1'), ('1.151.0.1', '1.157.0.1'), ('1.151.0.1', '1.158.0.1'), ('1.151.0.1', '1.159.0.1'), ('1.151.0.1', '1.160.0.1'), ('1.151.0.1', '1.161.0.1'), ('1.156.0.1', '1.160.0.1'), ('1.156.0.1', '1.161.0.1'), ('1.156.0.1', '1.157.0.1'), ('1.156.0.1', '1.158.0.1'), ('1.156.0.1', '1.159.0.1')]
    translate = {'1.151.0.1': 'BGW-LEE', '1.152.0.1': 'FW-LEE', '1.153.0.1': 'GW-LEE', '1.154.0.1': 'GW-HCI', '1.155.0.1': 'FW-HCI', '1.156.0.1': 'BGW-HCI', '1.157.0.1': 'OCT', '1.158.0.1': 'OX', '1.159.0.1': 'BS', '1.160.0.1': 'SB-LEE', '1.161.0.1': 'SB-HCI', '1.162.0.1': 'REF-LEE', '1.163.0.1': 'REF-HG', '1.164.0.1': 'REF-HCI', '1.165.0.1': 'REF-HPP'}

mode = args.mode
sleeptype = args.sleeptype

if args.no_edges == "1":
    sleep_edges = [sleep_edges[0]]
elif args.no_edges == "2":
    sleep_edges = sleep_edges[0:2]
elif args.no_edges == "all":
    sleep_edges = sleep_edges

hysterisis = args.hyst
linkmargin = args.linkmargin
interval = args.interval
wait_time = args.wait_time
wake_delay = args.wake_delay
dist_hyst = args.dist_hyst
max_util = args.max_util

nodes = list(translate.keys())
last_sleep_edge_bws = [None] * len(sleep_edges)


# main function that is called when the controller is started
def main():
    global topo, timestep

    topo = read_topology()
    counter = 0

    congestion_socket = socket.socket()
    congestion_socket.bind(('', 2024))
    congestion_socket.listen(5)
    congestion_socket.settimeout(0.1)

    start_time = time.time() - start_proc

    print(f"start took: {start_time}")

    time.sleep(max(0,wait_time-start_time))

    # main control loop
    for i in range(0, 120, interval):

        start = time.time()
        timestep = i+wait_time

        if counter == 0:
            traffic_step()
        else:
            counter -= 1
            print(counter)

        new_counter = check_congestion(congestion_socket, dist_hyst)

        if new_counter > counter:
            counter = new_counter
            
        end = time.time()
        if (end - start) > interval:
            print(f"Warning: timestep {i} took {end - start} seconds")

        time.sleep(max(0, interval - (end - start)))

    # wake network up again
    print("wake all")
    for node in nodes: 
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((node, 2023))
        s.sendall(f"wake all 0".encode())
        s.close()

    time.sleep(10)

    calculate_sleeptime()
    
    return


# check if congestion signal is received
def check_congestion(sock, dist_hyst):
    wake_all = True
    counter = 0
    try:
        while True:
            con, addr = sock.accept()
            print(f"Connection from {addr}")
            print(f"time of congestion: {time.time()}")
            print(con.recv(1024).decode())
            counter = dist_hyst
            if wake_all:
                for node in nodes: 
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((node, 2023))
                    s.sendall(f"wake all {wake_delay}".encode())
                    s.close()
                for edge in topo.edges():
                    topo[edge[0]][edge[1]]["sleep"] = False
                wake_all = False
                    
    except:
        print("no connection")
    
    return counter


# calculate the sleeptime of the links
def calculate_sleeptime():
    global translate, topo
    sleeptime = []
    start = {}

    for edge in topo.edges():
        edge = sorted(edge)
        edge_name = f"{translate[edge[0]]} - {translate[edge[1]]}"
        topo_sleeptime = topo[edge[0]][edge[1]]["sleeptime"]
        start[edge_name] = []
        if len(topo_sleeptime) > 1:
            start_element = topo_sleeptime[0]
            for i in range(len(topo_sleeptime)-1):
                if topo_sleeptime[i] + interval == topo_sleeptime[i+1]:
                    continue
                else:
                    start[edge_name].append((start_element, topo_sleeptime[i]))
                    start_element = topo_sleeptime[i+1]
            start[edge_name].append((start_element, topo_sleeptime[-1]))
        elif len(topo_sleeptime) == 1:
            start[edge_name].append((topo_sleeptime[0], topo_sleeptime[0]))
        sleeptime.append(len(topo_sleeptime)/120.0 * interval * 100)
        print(f"{edge_name}: {sleeptime[-1]} %")

    print(start)
    print(f"Average Sleeptime: {sum(sleeptime)/len(sleeptime)} %")

    return


# controller loop step
def traffic_step():
    global last_sleep_edge_bws, timestep

    elements = read_traffic()

    G = create_graph(elements)
    
    if len(G.edges()) == 0:
        return

    for index, sleep_edge in enumerate(sleep_edges):
        if topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
            topo[sleep_edge[0]][sleep_edge[1]]["sleeptime"].append(timestep)
        if sleep_edge not in G.edges():
            G.add_edges_from([(sleep_edge[0], sleep_edge[1], last_sleep_edge_bws[index][0])])
            G.add_edges_from([(sleep_edge[1], sleep_edge[0], last_sleep_edge_bws[index][1])])
        else:
            last_sleep_edge_bws[index] = (G[sleep_edge[0]][sleep_edge[1]],G[sleep_edge[1]][sleep_edge[0]])


    print_links(G, sleep_edges)
    
    edges_to_sleep = get_links_to_sleep(sleep_edges, G)
    edges_to_wake = get_links_to_wake(sleep_edges, G)

    if len(edges_to_wake) > 0:
        print(f"time of congestion: {time.time()}")

    if mode == "smart":
        edges_to_sleep = optimize_link_sleep(edges_to_sleep, G) 

    command_list = check_link_state(edges_to_sleep, edges_to_wake, G)

    if len(command_list) > 0:
        start = time.time()
        for command in command_list:
            command.start()
        for command in command_list:
            command.join()
        end = time.time()
        print(end - start)

    return


# Reads the topology from the OSPF database
def read_topology():
    temp_graph = create_graph(read_traffic())
    link_added = set()
    graph = nx.Graph()
    for edge in temp_graph.edges():
        if edge in link_added:
            continue
        graph.add_edge(edge[0],edge[1],ip=temp_graph[edge[0]][edge[1]]["ip"], sleep=False, counter=0, sleeptime=[])
        link_added.add((edge[1],edge[0]))
    for edge in graph.edges():
        print(graph[edge[0]][edge[1]])
    return graph


# Reads the traffic information from the OSPF database
def read_traffic():
    ospf = os.popen(f'echo -e "show ip ospf database opaque-area" | vtysh').read()
    #print(ospf)
    ospf = ospf.split("LS age")[1:]
    elements = [None] * len(ospf)

    type = 0
    for link_no, link in enumerate(ospf):
        for index, line in enumerate(link.split("\n")):
            if "Opaque-Type " in line:
                type = int(line.split()[1].strip())
            if type != 1:
                continue
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
            if "Utilized Bandwidth" in line:
                elements[link_no]["usage"] = float(line.split(":")[1].strip().split()[0])
            if "Maximum Bandwidth" in line:
                elements[link_no]["bw"] = float(line.split(":")[1].strip().split()[0])

        elements[link_no]["avail"] = max(0, elements[link_no]["bw"] - elements[link_no]["usage"])

    if None in elements:
        elements = elements[0:elements.index(None)]
    return elements


# Creates a Graph object out of the information read out of the OSPF database
def create_graph(elements):

    nodes = set([i["router_ip"] for i in elements])

    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    link_ids = set()
    edges = []
    for index, link in enumerate(elements):
        if "Multiaccess" in link["link_type"]:
            for link2 in elements[index+1:]:
                if link["link_id"] == link2["link_id"]:
                    if link["link_id"] in link_ids:
                        break
                    
                    edges, link_ids = add_link(link, link2, edges, link_ids)
                    
                    
        if "Point-to-point" in link["link_type"]:
            for link2 in elements[index+1:]:
                if link["remote_ip"] == link2["link_ip"]:
                    if link["link_ip"] in link_ids:
                        break

                    edges, link_ids = add_link(link, link2, edges, link_ids)

        
    G.add_edges_from(edges)
    return G


# Helper function to add a link to the list of edges to add to the graph
def add_link(link, link2, edges, link_ids):

    edges.append((link["router_ip"], link2["router_ip"], 
        {"ip": {f"{link['router_ip']}": link["link_ip"], f"{link2['router_ip']}": link2["link_ip"]},
            "avail": link['avail'],
            "usage": link['usage'],
            "max_bw": link['bw']}))
    
    link_ids.add(link["link_id"])

    edges.append((link2["router_ip"], link["router_ip"], 
        {"ip": {f"{link2['router_ip']}": link2["link_ip"], f"{link['router_ip']}": link["link_ip"]},
            "avail": link2['avail'],
            "usage": link2['usage'],
            "max_bw": link2['bw']}))

    link_ids.add(link2["link_id"])

    return edges, link_ids


# Decide which links can be put to sleep
def get_links_to_sleep(sleep_edges, G):
    global linkmargin

    edges_to_sleep = []

    for index, sleep_edge in enumerate(sleep_edges):

        minimum = [0] * len(sleep_edge)
        for i, node in enumerate(sleep_edge):
            if node not in G.nodes():
                break
            min_avail_list = []
            for neigh in nx.all_neighbors(G, node):
                if neigh in sleep_edge:
                    continue
                margin = G[node][neigh]["max_bw"] * linkmargin
                min_avail_list.append(max(0, G[node][neigh]["avail"]-margin))

            if len(min_avail_list) == 0:
                break
            minimum[i] = min(min_avail_list)

        if G[sleep_edge[0]][sleep_edge[1]]["usage"] < minimum[0] and G[sleep_edge[1]][sleep_edge[0]]["usage"] < minimum[1]:
            edges_to_sleep.append(sleep_edge)

    return edges_to_sleep


# Decide which links need to wake up
def get_links_to_wake(sleep_edges, G):
    global linkmargin

    edges_to_wake = []

    avail_perc = min([G[edge[0]][edge[1]]["avail"]/G[edge[0]][edge[1]]["max_bw"] for edge in G.edges()])

    if avail_perc < linkmargin:
       edges_to_wake = sleep_edges.copy()

    return edges_to_wake


# orders links by utilization and removes loaded links from the list
def optimize_link_sleep(edges_to_sleep, G):
    global max_util
    score = [None] * len(edges_to_sleep)
    for index, edge in enumerate(edges_to_sleep):
        score1 = G[edge[0]][edge[1]]["avail"] / G[edge[0]][edge[1]]["max_bw"]
        score2 = G[edge[1]][edge[0]]["avail"] / G[edge[1]][edge[0]]["max_bw"]
        score[index] = (min(score1, score2), edge)
    
    score.sort(reverse=True)
    print(score)
    opt_edges_to_sleep = []
    for score, edge in score:
        if score < (1-max_util):
            continue
        opt_edges_to_sleep.append(edge)
    return opt_edges_to_sleep


# check if link state needs to be changed and if it will remain connected after the change 
def check_link_state(edges_to_sleep, edges_to_wake, G):
    global topo, translate, timestep, sleeptype, hysterisis

    print_string = ""
    command_list = []

    for sleep_edge in topo.edges():
        if topo[sleep_edge[0]][sleep_edge[1]]["counter"] > 0:
            topo[sleep_edge[0]][sleep_edge[1]]["counter"] -= 1

    for sleep_edge in edges_to_wake:
        print_string += "\n"
        print_string += f"{translate[sleep_edge[0]]} - {translate[sleep_edge[1]]}: \t"
        topo[sleep_edge[0]][sleep_edge[1]]["counter"] = hysterisis
        print_string += f"Available too low: -> wake up \t"

        if not topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
            print_string += "Awake already sent"
            continue

        command_list.append(Process(target=send_command, args=("wake", sleep_edge, G)))
        
        topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = False

    for sleep_edge in edges_to_sleep:

        if sleep_edge in edges_to_wake:
            continue

        print_string += "\n"
        print_string += f"{translate[sleep_edge[0]]} - {translate[sleep_edge[1]]}: \t"
        if topo[sleep_edge[0]][sleep_edge[1]]["counter"] > 0:
            print_string += "set to sleep -> wakeup in progress"
            continue
        if topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
            print_string += "Sleep command already sent"
            continue
        if check_connectedness(sleep_edge) == False:
            print_string += f"Not connected anymore"
            continue
        print_string += "set to sleep"

        if sleeptype == "weightsleep":
            command_list.append(Process(target=send_command, args=("weightsleep", sleep_edge, G)))
        else:
            command_list.append(Process(target=send_command, args=("sleep", sleep_edge, G)))

        topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = True
        topo[sleep_edge[0]][sleep_edge[1]]["sleeptime"].append(timestep)


    print(print_string)
    return command_list


# Check if the network is still connected after setting the link to sleep
def check_connectedness(sleep_edge):
    global topo
    H=topo.copy()
    for edge in H.edges():
        if H[edge[0]][edge[1]]["sleep"] == True:
            H.remove_edge(edge[0],edge[1])
    
    H.remove_edge(sleep_edge[0],sleep_edge[1])
    return nx.is_connected(H)


# Sends the command to the router to sleep or wake up the link
def send_command(command, sleep_edge, G):
    
    for router in sleep_edge:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"{command} {G[sleep_edge[0]][sleep_edge[1]]['ip'][router]} {wake_delay}".encode())
            s.close()


# Prints the links and traffic amounts of the graph and marks the monitored links
def print_links(G, sleep_edges):
    global translate

    already_printed = set()
    print_string = ""
    monitored_string = "Monitored: \n"

    for edge in G.edges():
    
        if edge in already_printed:
            continue
        
        already_printed.add(edge[::-1])
        links = [edge, edge[::-1]]
        if edge in sleep_edges or edge[::-1] in sleep_edges:
            for link in links:
                ips = link
                link_info = G[link[0]][link[1]]
                max_bw = link_info["max_bw"]
                monitored_string += f"{translate[ips[0]]} - {translate[ips[1]]}: Avail: {round(link_info['avail']*100/max_bw)}, Usage: {round(link_info['usage']*100/max_bw)} \t"
            monitored_string += "\n"
        else:
            for link in links:
                ips = link
                link_info = G[link[0]][link[1]]
                max_bw = link_info["max_bw"]
                print_string += f"{translate[ips[0]]} - {translate[ips[1]]}: Avail: {round(link_info['avail']*100/max_bw)}, Usage: {round(link_info['usage']*100/max_bw)} \t"
            print_string += "\n"

    print(print_string)
    print(monitored_string)


if __name__ == "__main__":
    
    main()
