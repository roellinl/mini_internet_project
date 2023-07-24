#!/usr/bin/python3
import time
import os
import sys
import asyncio

in_progress={}


async def main(address):
    server = await asyncio.start_server(
        receive_command, address[0], address[1])

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()
    return


async def receive_command(reader, writer):
    global in_progress, ip_to_intf
    ts = time.time()
    data = await reader.read(1024)
    output = "empty"
    print(data)

    if data.decode() == "wake all":
        await wake_all(ts)
        writer.close()
        await writer.wait_closed()
        return
    
    command, link = data.decode().split()

    if link not in ip_to_intf:
        ip_to_intf = get_ip_to_intf()

    intf = ip_to_intf[link]
    in_progress[intf] = ts

    print(in_progress,flush=True)
    print(f"command: {command}, LinkId: {link}, Interface: {intf}",flush=True)
    
    if command == "sleep" or command == "weightsleep":
        await sleep(ts, command, intf)
        
    elif command == "wake":
        print(f"Add artificial delay of {delay} seconds before wakeup", flush=True)
        await asyncio.sleep(delay)
        await wake(ts, intf)
    else:
        output = "unkown command"
        print(output,flush=True)

    print("Close the connection")
    writer.close()
    await writer.wait_closed()
    return


async def wake_all(ts):
    global in_progress, ip_to_intf
    ip_to_intf = get_ip_to_intf()
    for intf in ip_to_intf.values():
        in_progress[intf] = ts
        print(in_progress,flush=True)
    print(f"Add artificial delay of {delay} seconds before wakeup")
    await asyncio.sleep(delay)
    for intf in ip_to_intf.values():
        print(f"wake all {intf}",flush=True)
        await wake(ts, intf)
    return


async def sleep(ts, command, intf):
    bw_info = vtysh_command(f"show interface {intf}").split("\n")

    print(bw_info,flush=True)
    for line in bw_info:
        print(line,flush=True)
        if "Maximum Bandwidth" in line:
            max_bw = float(line.lstrip().split()[2])
            break
    print(f"max_bw: {max_bw}", flush=True)

    if command == "weightsleep":
        if in_progress[intf] == ts:
            output = vtysh_command(f"conf t \n interface {intf} \n ip ospf cost 65535 \n exit \n exit \n exit \n")
        else:
            print(f"skipped cost because of newer command {in_progress[intf]},flush=True")
        await asyncio.sleep(5)

    if in_progress[intf] == ts:
        output = vtysh_command(f"conf t \n interface {intf} \n link-params \n ava-bw {max_bw} \n use-bw 0 \n exit \n shutdown \n exit \n exit \n exit \n")
    else:
        print(f"skipped because of newer command {in_progress[intf]},flush=True")

    return


async def wake(ts, intf):
    if in_progress[intf] == ts:
        output = vtysh_command(f"conf t \n interface {intf} \n ip ospf cost 1 \n no shutdown \n exit \n exit \n exit \n")
    return


def vtysh_command(command):
    return os.popen(f'echo -e "{command} \n exit \n" | vtysh').read()


def get_ip_to_intf():
    ip_to_intf = {}
    link_ip = vtysh_command(f"show interface brief \n exit \n")

    print(link_ip.split("\n"))

    for interface in link_ip.split("\n")[7:-3]:
        print(interface.split())
        if len(interface.split()) < 4:
            continue
        linkid = interface.split()[3].split("/")[0]
        ip_to_intf[linkid] = interface.split()[0]

    print(ip_to_intf,flush=True)
    return ip_to_intf


if __name__=="__main__":
    time.sleep(10)
    delay = 10
    if len(sys.argv) == 2:
        delay = float(sys.argv[1])

    ip_to_intf = get_ip_to_intf()
    address = ("", 2023)
    asyncio.run(main(address))
