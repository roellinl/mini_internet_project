import os
import networkx as nx
import time
import socket
import sys

sleep_edges = [("1.151.0.1","1.154.0.1"),("1.151.0.1","1.153.0.1")]

last_sleep_edge_bw = [None] * len(sleep_edges)
sleep_edge_bw = [None] * len(sleep_edges)



translate = {"1.151.0.1": "ZURI", "1.152.0.1": "BASE", "1.153.0.1": "GENE", "1.154.0.1": "LUGA", "1.155.0.1": "MUNI", "1.156.0.1": "LYON", "1.157.0.1": "VIEN", "1.158.0.1": "MILA"}
sleeptype = sys.argv[1]

def main():

    global topo
    topo = read_topology()

    for i in range(120):
        traffic_step()
        print("\n",flush=True)
        time.sleep(1)

    for sleep_edge in sleep_edges:
        for router in sleep_edge:
            print(router)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"wake all".encode())
            s.close()

    time.sleep(10)


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

    for edge in G.edges():
        print_string = ""

        if edge in already_printed:
            continue

        if edge in sleep_edges or edge[::-1] in sleep_edges:
            print("Monitored Edge: ")

        already_printed.add(edge[::-1])
        links = [edge, edge[::-1]]
        for link in links:
            ips = link
            link_info = G[link[0]][link[1]]
            max_bw = link_info["max_bw"]
            print_string += f"{translate[ips[0]]} - {translate[ips[1]]}: Avail: {round(link_info['avail']*100/max_bw)}, Usage: {round(link_info['usage']*100/max_bw)}   "
        print(print_string)


"""
Decides on what to do with the given traffic for each sleep edge
"""
def react_to_traffic(sleep_edge, sleep_edge_bw, G):
    global topo
 
    avail_perc = min([G[edge[0]][edge[1]]["avail"]/G[edge[0]][edge[1]]["max_bw"] for edge in G.edges()])

    topo[sleep_edge[0]][sleep_edge[1]]["counter"] -= 1 
    topo[sleep_edge[1]][sleep_edge[0]]["counter"] -= 1

    if avail_perc < 0.2:
        print(f"Available too low: {avail_perc} -> wake up")
        
        topo[sleep_edge[0]][sleep_edge[1]]["counter"] = 10
        topo[sleep_edge[1]][sleep_edge[0]]["counter"] = 10

        if not topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
            print("Awake already sent")
            return
        for router in sleep_edge:
            print(router)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            s.sendall(f"wake {sleep_edge_bw[0]['ip'][router]}".encode())
            s.close()
        topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = False
        topo[sleep_edge[1]][sleep_edge[0]]["sleep"] = False
        return

    
    minimum = [0] * len(sleep_edge)
    for i, node in enumerate(sleep_edge):
        if node not in G.nodes():
            return
        min_avail_list = []
        for neigh in nx.all_neighbors(G, node):
            if neigh in sleep_edge:
                continue
            min_avail_list.append(G[node][neigh]["avail"])
        if len(min_avail_list) == 0:
            return
        minimum[i] = min(min_avail_list)

    if sleep_edge_bw[0]["usage"] < minimum[0] and sleep_edge_bw[1]["usage"] < minimum[1]:
        if topo[sleep_edge[0]][sleep_edge[1]]["counter"] > 0:
            print("set to sleep -> wakeup in progress")
            return
        if topo[sleep_edge[0]][sleep_edge[1]]["sleep"]:
            print("Sleep command already sent")
            return
        print("set to sleep")
        for router in sleep_edge:
            print(router)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((router, 2023))
            if sleeptype == "weightsleep":
                s.sendall(f"weightsleep {sleep_edge_bw[0]['ip'][router]}".encode())
            else:
                s.sendall(f"sleep {sleep_edge_bw[0]['ip'][router]}".encode())
            s.close()
        topo[sleep_edge[0]][sleep_edge[1]]["sleep"] = True
        topo[sleep_edge[1]][sleep_edge[0]]["sleep"] = True


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


def read_topology():
    graph = create_graph(read_traffic())
    for edge in graph.edges():
        graph[edge[0]][edge[1]].pop("avail")
        graph[edge[0]][edge[1]].pop("usage")
        graph[edge[0]][edge[1]]["sleep"] = False
        graph[edge[0]][edge[1]]["counter"] = 0
    for edge in graph.edges():
        print(graph[edge[0]][edge[1]])
    return graph


"""
Main function that is called every second
"""
def traffic_step():
    global last_sleep_edge_bw

    elements = read_traffic()

    G = create_graph(elements)
    
    if len(G.edges()) == 0:
        return

    for index, sleep_edge in enumerate(sleep_edges):
        if sleep_edge not in G.edges():
            sleep_edge_bw[index] = last_sleep_edge_bw[index]
        else:
            sleep_edge_bw[index] = (G[sleep_edge[0]][sleep_edge[1]],G[sleep_edge[1]][sleep_edge[0]])
            last_sleep_edge_bw[index] = sleep_edge_bw[index]


    print_links(G, sleep_edges)

    for index, sleep_edge in enumerate(sleep_edges):
        print(sleep_edge)
        react_to_traffic(sleep_edge, sleep_edge_bw[index], G)
    
    return


if __name__ == "__main__":
    
    main()
    