#!/usr/bin/env python3

from sys import argv, exit
from socket import *
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE, SelectorKey
from types import SimpleNamespace
import json

selector = DefaultSelector()

users: dict[str, str] = {"A": "ok", "B": "ook", "C": "", "D": "", "E": "", "F": ""}
onlineUserSockets: dict[str, socket] = {}

def accept_client(sock: socket):
    conn, addr = sock.accept()  # Should be ready to read
    msg = conn.recv(1024).decode()
    user_credentials: dict = json.loads(msg)
    username = user_credentials['Username']
    password = user_credentials['Password']
    newuser = user_credentials['Newuser']
    if not newuser and not (username in users.keys() and password == users[username]):
        conn.sendall("invalid".encode())
        conn.close()
        return
    if newuser:
        if username in users.keys():
            conn.sendall("invalid".encode())
            conn.close()
            return
        else:
            users[username] = password

    print(f"Accepted connection from {addr} with username {username}")
    onlineUserSockets[username] = conn
    conn.sendall('You are now logged in.'.encode())
    conn.setblocking(False)
    data = SimpleNamespace(username=username, addr=addr, inb=b"", outb=b"")
    events = EVENT_READ | EVENT_WRITE
    selector.register(conn, events, data=data)

def serve_client(key: SelectorKey, mask: bool):
    sock: socket = key.fileobj
    data: SimpleNamespace = key.data
    try:
        if mask & EVENT_READ:
            recv_data = sock.recv(1024)  # Should be ready to read
            if recv_data != b'':
                data.outb += recv_data
                msg = json.loads(recv_data.decode())
                if msg['Recipient'] not in users:
                    sock.sendall('invalid_recipient'.encode())
                    return
                elif msg['Recipient'] not in onlineUserSockets:
                    pass # todo, must save message in queue - dict(username, [messages to be sent sorted by timestamp]) and send when user comes online (in accept_client when they log in)
                else: # user is online
                    onlineUserSockets[data.username].sendall(recv_data)
                print(f"Client {data.username} to {msg['Recipient']}:", msg['Message'])
            else:
                print(f"Closing connection to {data.username} ({data.addr})")
                selector.unregister(sock)
                sock.close()
        if mask & EVENT_WRITE:
            if data.outb:
                response = ""#input(f"ToClient {data.username}: ")
                if response == "": response = "received"
                data.outb = response.encode()
                # print(f"Echoing {data.outb!r} to {data.addr}")
                sent = sock.send(data.outb)  # Should be ready to write
                data.outb = data.outb[sent:]
    except BrokenPipeError as e:
        print(f"Client {data.username} closed the connection.")

# ------------------------------------------------- #

if len(argv) != 3:
    print(f"Usage: {argv[0]} <host> <port>")
    exit(1)

# setup server
host, port = argv[1], int(argv[2])
with socket(AF_INET, SOCK_STREAM) as lsock:
    lsock.bind((host, port))
    lsock.listen()
    print(f"Listening on {(host, port)}")

    # lsock.setblocking(False)
    selector.register(fileobj=lsock, events=EVENT_READ, data=None)

    try:
        events = selector.select(timeout=None)
        # print(events)
        while True:
            events = selector.select(timeout=None)
            for key, mask in events:
                if key.data is None:
                    accept_client(key.fileobj)
                else:
                    serve_client(key, mask)
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    finally:
        selector.close()
