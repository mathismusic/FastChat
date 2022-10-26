#!/usr/bin/env python3

from sys import argv, exit
from socket import *
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE, SelectorKey
from types import SimpleNamespace

selector = DefaultSelector()


def accept_client(sock: socket):
    conn, addr = sock.accept()  # Should be ready to read
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = SimpleNamespace(addr=addr, inb=b"", outb=b"")
    events = EVENT_READ | EVENT_WRITE
    selector.register(conn, events, data=data)


def serve_client(key: SelectorKey, mask: bool):
    sock: socket = key.fileobj
    data: SimpleNamespace = key.data
    if mask & EVENT_READ:
        recv_data = sock.recv(1024)  # Should be ready to read
        if recv_data is not None:
            data.outb += recv_data
            print(f"Client {data.addr}:", recv_data.decode())
        else:
            print(f"Closing connection to {data.addr}")
            selector.unregister(sock)
            sock.close()
    if mask & EVENT_WRITE:
        if data.outb:
            response = input(f"ToClient {data.addr}: ")
            if response == "": response = "Message Received."
            data.outb = bytes(response.encode())
            # print(f"Echoing {data.outb!r} to {data.addr}")
            sent = sock.send(data.outb)  # Should be ready to write
            data.outb = data.outb[sent:]

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

    lsock.setblocking(False)
    selector.register(fileobj=lsock, events=EVENT_READ, data=None)

    try:
        events = selector.select(timeout=None)
        print(events)
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
