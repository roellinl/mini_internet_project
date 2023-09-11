#!/usr/bin/python3
import time
import os
import sys
import asyncio
import json

in_progress={}
last_ospf_cost = {}
default_delay = 10

async def main(address):
    server = await asyncio.start_server(
        receive_command, address[0], address[1])

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()
    return


async def receive_command(reader, writer):
    global in_progress, ip_to_intf, default_delay

    ts = time.time()
    data = await reader.read(1024)
    output = "empty"
    command = data.decode()
    print(f"command: {command}",flush=True)

    if "wake all" in command:
        if len(command.split()) == 3:
            delay = float(command.split()[2])
        else:
            delay = default_delay

        await wake_all(ts, delay)
        writer.close()
        await writer.wait_closed()
        return
    
    link_cmd = command.split()[0]
    link = command.split()[1]

    if len(command.split()) == 3:
        delay = float(command.split()[2])
    else:
        delay = default_delay

    if link not in ip_to_intf:
        ip_to_intf = get_ip_to_intf()

    intf = ip_to_intf[link]
    if intf in in_progress and in_progress[intf][1] == link_cmd:
        print(f"skipped because of same link_cmd {in_progress[intf][1]}")
        return
    in_progress[intf] = (ts, link_cmd)

    print(in_progress,flush=True)
    print(f"link_cmd: {link_cmd}, LinkId: {link}, Interface: {intf}",flush=True)
    
    if link_cmd == "sleep" or link_cmd == "weightsleep":
        await sleep(ts, link_cmd, intf)
        
    elif link_cmd == "wake":
        await wake(ts, intf, delay)
    else:
        output = "unkown link_cmd"
        print(output,flush=True)

    print("Close the connection")
    writer.close()
    await writer.wait_closed()
    return


async def wake_all(ts, delay):
    global in_progress, ip_to_intf

    ip_to_intf = get_ip_to_intf()
    tasks = []
    for intf in ip_to_intf.values():
        if intf in in_progress and in_progress[intf][1] == "wake":
            print(f"skipped because of same command {in_progress[intf][1]}")
            continue
        in_progress[intf] = (ts, "wake")
        print(f"wake all {intf}",flush=True)
        print(f"in progress: {in_progress}",flush=True)

        tasks.append(asyncio.create_task(wake(ts, intf, delay)))
    #print(f"Add artificial delay of {delay} seconds before wakeup", flush=True)
    for task in tasks:
        await task

    #for intf in ip_to_intf.values():
    #    await wake(ts, intf, 0)
    return


async def sleep(ts, command, intf):
    bw_info = vtysh_command(f"show interface {intf}").split("\n")

    #print(bw_info,flush=True)
    for line in bw_info:
        print(line,flush=True)
        if "Maximum Bandwidth" in line:
            max_bw = float(line.lstrip().split()[2])
            break
    print(f"max_bw: {max_bw}", flush=True)

    if command == "weightsleep":
        if in_progress[intf][0] == ts:
            cost_string = vtysh_command(f"show ip ospf interface {intf} json \n exit \n")
            cost_string = cost_string[cost_string.index("{"):cost_string.rindex("}")+2]
            cost = json.loads(cost_string)["interfaces"][intf]["cost"]
            print(f"cost: {cost} intf", flush=True)
            if cost != 65535:
                last_ospf_cost[intf] = cost
            output = vtysh_command(f"conf t \n interface {intf} \n ip ospf cost 65535 \n exit \n exit \n exit \n")
        else:
            print(f"skipped cost because of newer command {in_progress[intf][0]},flush=True")
        await asyncio.sleep(1)

    if in_progress[intf][0] == ts:
        output = vtysh_command(f"conf t \n interface {intf} \n shutdown \n exit \n exit \n exit \n")
    else:
        print(f"skipped because of newer command {in_progress[intf][0]},flush=True")

    return


async def wake(ts, intf, delay):
    if delay != 0:
        print(f"Add artificial delay of {delay} seconds before wakeup", flush=True)
        await asyncio.sleep(delay)

    if in_progress[intf][0] == ts:
        if intf not in last_ospf_cost.keys():
            last_ospf_cost[intf] = 1
        output = vtysh_command(f"conf t \n interface {intf} \n no shutdown \n  ip ospf cost {last_ospf_cost[intf]} \n exit \n exit \n exit \n")
        #output += vtysh_command(f"clear ip ospf interface {intf} \n exit \n")
        #output += vtysh_command(f"conf t \n router ospf \n mpls-te on \n exit \n exit \n exit \n")
    return


def vtysh_command(command):
    return os.popen(f'echo -e "{command} \n exit \n" | vtysh').read()


def get_ip_to_intf():
    ip_to_intf = {}
    link_ip = vtysh_command(f"show interface brief \n exit \n")

    #print(link_ip.split("\n"))

    for interface in link_ip.split("\n")[7:-3]:
        #print(interface.split())
        if len(interface.split()) < 4:
            continue
        if "port_" in interface.split()[0]:
            linkid = interface.split()[3].split("/")[0]
            ip_to_intf[linkid] = interface.split()[0]

    print(ip_to_intf,flush=True)
    return ip_to_intf


if __name__=="__main__":
    
    time.sleep(10)

    if len(sys.argv)==2:
        default_delay = float(sys.argv[1])

    ip_to_intf = get_ip_to_intf()
    address = ("", 2023)
    asyncio.run(main(address))
