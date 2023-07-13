#!/usr/bin/python3
import time
import os
import sys
import asyncore

class Request_Handler(asyncore.dispatcher_with_send):

    def handle_read(self):
        data = self.recv(8192)
        if data:
            receive_command(data)

class Server(asyncore.dispatcher):

    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket()
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accepted(self, sock, addr):
        print('Incoming connection from %s' % repr(addr))
        handler = Request_Handler(sock)

def get_ip_to_intf():
    ip_to_intf = {}
    link_ip = os.popen(f'echo -e "show interface brief \n exit \n" | vtysh').read()
    print(link_ip.split("\n"))
    for interface in link_ip.split("\n")[7:-3]:
        print(interface.split())
        linkid = interface.split()[3].split("/")[0]
        ip_to_intf[linkid] = interface.split()[0]

    print(ip_to_intf,flush=True)
    return ip_to_intf

def wakeup(intf, delay):
    print(f"Add artificial delay of {delay} seconds before wakeup")
    time.sleep(delay)
    output = os.popen(f'echo -e "conf t \n interface {intf} \n no shutdown \n exit \n exit \n exit \n" | vtysh').read()
    return output

def receive_command(data):
    global ip_to_intf

    if data.decode() == "wake all":
        ip_to_intf = get_ip_to_intf()
        print(f"Add artificial delay of {delay} seconds before wakeup")
        time.sleep(delay)
        for intf in ip_to_intf.values():
            print(f"wake all {intf}",flush=True)
            output = os.popen(f'echo -e "conf t \n interface {intf} \n no shutdown \n exit \n exit \n exit \n" | vtysh').read()
        return
    
    command, link = data.decode().split()
    if link not in ip_to_intf:
        ip_to_intf = get_ip_to_intf()
    intf = ip_to_intf[link]
    print(f"command: {command}, LinkId: {link}, Interface: {intf}")
    if command == "sleep":
        max_bw = float(os.popen(f'echo -e "show interface {intf}" | vtysh').read().split("\n")[19].lstrip().split()[2])
        output = os.popen(f'echo -e "conf t \n interface {intf} \n link-params \n ava-bw {max_bw} \n use-bw 0 \n exit \n exit \n exit \n exit \n" | vtysh').read()
        print(output, flush=True)
        output = os.popen(f'echo -e "conf t \n interface {intf} \n shutdown \n exit \n exit \n exit \n" | vtysh').read()
    elif command == "wake":
        wakeup(intf, delay)
    else:
        print("unkown command")
    print(output,flush=True)




time.sleep(10)
delay = 10
if len(sys.argv) == 2:
    delay = float(sys.argv[1])

ip_to_intf = get_ip_to_intf()
server = Server("", 2023)
asyncore.loop()

