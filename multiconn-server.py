#!/usr/bin/env python3

from sys import argv, exit
import socket
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE, SelectorKey
from types import SimpleNamespace
import json

users: dict[str, str] = {"A": "ok", "B": "ook", "C": "c", "D": "d", "E": "e", "F": "f"}
onlineUserSockets: dict[str, socket.socket] = {}

class Server:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = "192.168.103.215"  # The server's hostname or IP address
        self.PORT = 61001  # The port used by the server
        self.selector = DefaultSelector()

        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()
        print(f"Listening on {(self.HOST, self.PORT)}")

    def accept_client(self):
        conn, addr = self.sock.accept()  # Should be ready to read
        msg = conn.recv(1024).decode()
        user_credentials: dict = json.loads(msg)
        username = user_credentials['Username']
        password = user_credentials['Password']
        newuser = user_credentials['Newuser']
            
        if newuser:
            if username in users.keys():
                conn.sendall("invalid".encode())
                conn.close()
                return
            else:
                users[username] = password
        elif (username not in users.keys() or password != users[username]):
            conn.sendall("invalid".encode())
            conn.close()
            return

        print(f"Accepted connection from {addr} with username {username}")
        onlineUserSockets[username] = conn # change to bool = True
        conn.sendall('valid'.encode())
        conn.setblocking(False)
        data = SimpleNamespace(username=username, addr=addr, inb=b"", outb=b"")
        events = EVENT_READ | EVENT_WRITE
        self.selector.register(conn, events, data=data)

    def serve_client(self, key: SelectorKey, mask: bool):
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
                        onlineUserSockets[msg['Recipient']].sendall(recv_data)
                    print(f"Client {data.username} to {msg['Recipient']}:", msg['Message'])
                else:
                    print(f"Closing connection {data.username} ({data.addr}) - username {data.username}")
                    self.selector.unregister(sock)
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

    def run(self):
        # lsock.setblocking(False)
        self.selector.register(fileobj=self.sock, events=EVENT_READ, data=None)

        try:
            while True:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept_client(key.fileobj)
                    else:
                        self.serve_client(key, mask)
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        finally:
            self.selector.close()

server = Server()
server.run()


