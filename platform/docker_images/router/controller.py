import os
import networkx as nx
import time
import socket
import sys
from multiprocessing import Process

sleep_edges = [("1.151.0.1","1.154.0.1"),("1.151.0.1","1.153.0.1"),("1.151.0.1","1.152.0.1"),("1.151.0.1","1.157.0.1"),("1.151.0.1","1.155.0.1"),("1.153.0.1","1.152.0.1"),("1.152.0.1","1.155.0.1"),
               ("1.153.0.1","1.156.0.1"),("1.154.0.1","1.158.0.1"),("1.152.0.1","1.156.0.1"),("1.154.0.1","1.157.0.1"),("1.153.0.1","1.154.0.1")]

if len(sys.argv) >= 3:
    experiment = sys.argv[2]
    if experiment == "1":
        sleep_edges = [sleep_edges[0]]
    elif experiment == "2":
        sleep_edges = sleep_edges[0:2]
    elif experiment == "all":
        sleep_edges = sleep_edges



last_sleep_edge_bws = [None] * len(sleep_edges)
sleep_edge_bws = [None] * len(sleep_edges)

translate = {"1.151.0.1": "ZURI", "1.152.0.1": "BASE", "1.153.0.1": "GENE", "1.154.0.1": "LUGA", "1.155.0.1": "MUNI", "1.156.0.1": "LYON", "1.157.0.1": "VIEN", "1.158.0.1": "MILA"}
sleeptype = sys.argv[1]
timestep = 0

def main():
    global topo, timestep

    topo = read_topology()

    for i in range(120):
        timestep = i
        traffic_step()
        time.sleep(1)

    print("wake all")
    for sleep_edge in sleep_edges:
        for router in sleep_edge:        
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"wake all".encode())
            s.close()

    time.sleep(10)
    sleeptime = []
    start = {}
    for edge in topo.edges():
        edge_name = f"{translate[edge[0]]} - {translate[edge[1]]}"
        topo_sleeptime = topo[edge[0]][edge[1]]["sleeptime"]
        start[edge_name] = []
        if len(topo_sleeptime) > 1:
            start_element = topo_sleeptime[0]
            for i in range(len(topo_sleeptime)-1):
                if topo_sleeptime[i] + 1 == topo_sleeptime[i+1]:
                    continue
                else:
                    start[edge_name].append((start_element, topo_sleeptime[i]))
                    start_element = topo_sleeptime[i+1]
            start[edge_name].append((start_element, topo_sleeptime[-1]))
        elif len(topo_sleeptime) == 1:
            start[edge_name].append((topo_sleeptime[0], topo_sleeptime[0]))
        sleeptime.append(len(topo_sleeptime)/120.0 * 100)
        print(f"{edge_name}: {sleeptime[-1]} %")
    print(start)

    print(f"Average Sleeptime: {sum(sleeptime)/len(sleeptime)} %")


"""
Helper function to add a link to the list of edges to add to the graph
"""
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


"""
Creates a Graph object out of the information read out of the OSPF database
"""
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


"""
Prints the links and traffic amounts of the graph and marks the monitored links
"""
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


"""
Decide which links can be put to sleep
"""
def get_links_to_sleep(sleep_edges, sleep_edge_bws, G):

    edges_to_sleep = [False for i in range(len(sleep_edges))]
    
    for index, sleep_edge in enumerate(sleep_edges):
        sleep_edge_bw = sleep_edge_bws[index]
        minimum = [0] * len(sleep_edge)
        for i, node in enumerate(sleep_edge):
            if node not in G.nodes():
                break
            min_avail_list = []
            for neigh in nx.all_neighbors(G, node):
                if neigh in sleep_edge:
                    continue
                min_avail_list.append(G[node][neigh]["avail"])

            if len(min_avail_list) == 0:
                break
            minimum[i] = min(min_avail_list)

        if sleep_edge_bw[0]["usage"] < minimum[0] and sleep_edge_bw[1]["usage"] < minimum[1]:
            edges_to_sleep[index] = True

    return edges_to_sleep


"""
Decide which links need to wake up
"""
def get_links_to_wake(sleep_edges, G):
    edges_to_wake = [False for i in range(len(sleep_edges))]

    avail_perc = min([G[edge[0]][edge[1]]["avail"]/G[edge[0]][edge[1]]["max_bw"] for edge in G.edges()])

    if avail_perc < 0.2:
       edges_to_wake = [True for i in range(len(sleep_edges))]

    return edges_to_wake


""" 
check if link state needs to be changed and if it will remain connected after the change 
"""
def check_link_state(edges_to_sleep, edges_to_wake, sleep_edges, sleep_edge_bws):
    global topo, translate, timestep, sleeptype

    print_string = ""
    command_list = []

    for index, sleep_edge in enumerate(sleep_edges):
        sleep_edge_bw = sleep_edge_bws[index]
        print_string += "\n"
        print_string += f"{translate[sleep_edge[0]]} - {translate[sleep_edge[1]]}: \t"

        if topo[sleep_edge[0]][sleep_edge[1]]["counter"] > 0:
            topo[sleep_edge[0]][sleep_edge[1]]["counter"] -= 1

        if edges_to_wake[index] == True:

            topo[sleep_edge[0]][sleep_edge[1]]["counter"] = 10
            print_string += f"Available too low: -> wake up \t"

            if not topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
                print_string += "Awake already sent"
                continue

            command_list.append(Process(target=send_command, args=("wake", sleep_edge, sleep_edge_bw)))

            topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = False

        elif edges_to_sleep[index] == True:

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
                command_list.append(Process(target=send_command, args=("weightsleep", sleep_edge, sleep_edge_bw)))
            else:
                command_list.append(Process(target=send_command, args=("sleep", sleep_edge, sleep_edge_bw)))

            topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = True
            topo[sleep_edge[0]][sleep_edge[1]]["sleeptime"].append(timestep)

    print(print_string)
    return command_list


"""
Sends the command to the router to sleep or wake up the link
"""
def send_command(command, sleep_edge, sleep_edge_bw):
    
    for router in sleep_edge:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"{command} {sleep_edge_bw[0]['ip'][router]}".encode())
            s.close()


"""
Reads the traffic information from the OSPF database
"""
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
            if "Available Bandwidth" in line:
                elements[link_no]["avail"] = float(line.split(":")[1].strip().split()[0])
            if "Utilized Bandwidth" in line:
                elements[link_no]["usage"] = float(line.split(":")[1].strip().split()[0])
            if "Maximum Bandwidth" in line:
                elements[link_no]["bw"] = float(line.split(":")[1].strip().split()[0])


    if None in elements:
        elements = elements[0:elements.index(None)]
    return elements


"""
Check if the network is still connected after setting the link to sleep
"""
def check_connectedness(sleep_edge):
    global topo
    H=topo.copy()
    for edge in H.edges():
        if H[edge[0]][edge[1]]["sleep"] == True:
            H.remove_edge(edge[0],edge[1])
    
    H.remove_edge(sleep_edge[0],sleep_edge[1])
    return nx.is_connected(H)


"""
Reads the topology from the OSPF database
"""
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


"""
Main function that is called every second
"""
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
            sleep_edge_bws[index] = last_sleep_edge_bws[index]
        else:
            sleep_edge_bws[index] = (G[sleep_edge[0]][sleep_edge[1]],G[sleep_edge[1]][sleep_edge[0]])
            last_sleep_edge_bws[index] = sleep_edge_bws[index]


    print_links(G, sleep_edges)
    
    edges_to_sleep = get_links_to_sleep(sleep_edges, sleep_edge_bws, G)
    edges_to_wake = get_links_to_wake(sleep_edges, G)

    command_list = check_link_state(edges_to_sleep, edges_to_wake, sleep_edges, sleep_edge_bws)

    if len(command_list) > 0:
        start = time.time()
        for command in command_list:
            command.start()
        for command in command_list:
            command.join()
        end = time.time()
        print(end - start)

    return


if __name__ == "__main__":
    
    main()
    