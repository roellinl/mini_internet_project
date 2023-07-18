#!/usr/bin/python3
import time
import os
import sys
import asyncio


def get_ip_to_intf():
    ip_to_intf = {}
    link_ip = os.popen(f'echo -e "show interface brief \n exit \n" | vtysh').read()
    print(link_ip.split("\n"))
    for interface in link_ip.split("\n")[7:-3]:
        print(interface.split())
        if len(interface.split()) < 4:
            continue
        linkid = interface.split()[3].split("/")[0]
        ip_to_intf[linkid] = interface.split()[0]

    print(ip_to_intf,flush=True)
    return ip_to_intf

async def receive_command(reader, writer):
    data = await reader.read(1024)
    global ip_to_intf
    output = "empty"
    print(data)
    if data.decode() == "wake all":
        ip_to_intf = get_ip_to_intf()
        print(f"Add artificial delay of {delay} seconds before wakeup")
        await asyncio.sleep(delay)
        for intf in ip_to_intf.values():
            print(f"wake all {intf}",flush=True)
            output = os.popen(f'echo -e "conf t \n interface {intf} \n no shutdown \n exit \n exit \n exit \n" | vtysh').read()
        reader.close()
        await reader.wait_closed()
        writer.close()
        await writer.wait_closed()
        return
    
    command, link = data.decode().split()
    if link not in ip_to_intf:
        ip_to_intf = get_ip_to_intf()
    intf = ip_to_intf[link]
    print(f"command: {command}, LinkId: {link}, Interface: {intf}",flush=True)
    if command == "sleep":
        bw_info = os.popen(f'echo -e "show interface {intf}" | vtysh').read().split("\n")
        print(bw_info,flush=True)
        for line in bw_info:
            print(line,flush=True)
            if "Maximum Bandwidth" in line:
                max_bw = float(line.lstrip().split()[2])
                break
        print(f"max_bw: {max_bw}", flush=True)
        output = os.popen(f'echo -e "conf t \n interface {intf} \n link-params \n ava-bw {max_bw} \n use-bw 0 \n exit \n exit \n exit \n exit \n" | vtysh').read()
        print(output, flush=True)
        output = os.popen(f'echo -e "conf t \n interface {intf} \n shutdown \n exit \n exit \n exit \n" | vtysh').read()
    elif command == "wake":
        print(f"Add artificial delay of {delay} seconds before wakeup", flush=True)
        await asyncio.sleep(delay)
        output = os.popen(f'echo -e "conf t \n interface {intf} \n no shutdown \n exit \n exit \n exit \n" | vtysh').read()
    else:
        output = "unkown command"
    print(output,flush=True)
    print("Close the connection")
    reader.close()
    await reader.wait_closed()
    writer.close()
    await writer.wait_closed()



async def main(address):
    server = await asyncio.start_server(
        receive_command, address[0], address[1])

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Serving on {addrs}')

    async with server:
        await server.serve_forever()

time.sleep(10)
delay = 10
if len(sys.argv) == 2:
    delay = float(sys.argv[1])

ip_to_intf = get_ip_to_intf()
address = ("", 2023)
asyncio.run(main(address))
