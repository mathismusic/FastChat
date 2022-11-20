from sys import argv, exit
import socket
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE, SelectorKey
from types import SimpleNamespace
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from color_codes import *

# 192.168.103.215
onlineUserSockets: dict[str, socket.socket] = {}
users = {}
class Server:
    """Server class. Contains host address and port, 
    along with a connection to the PSQL server hosted locally."""
    def __init__(self) -> None:
        """Constructor, initializes to a default IP and port. Creates empty databases."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = "192.168.103.215"  # The server's hostname or IP address
        self.PORT = 61001 if len(argv) == 1 else 61002  # The port used by the server
        self.selector = DefaultSelector()
        self.userDBName = "users"

        self.databaseServer = psycopg2.connect(
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )

        self.databaseServer.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        curs = self.databaseServer.cursor()
        curs.execute("DROP DATABASE IF EXISTS " + self.userDBName)
        curs.execute("CREATE DATABASE " + self.userDBName)
        
        self.databaseServer.commit()
        curs.close()

        self.databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )


        curs = self.databaseServer.cursor()
        curs.execute("""CREATE TABLE IF NOT EXISTS usercreds (
                        userid SERIAL PRIMARY KEY,
                        username VARCHAR(256) NOT NULL,
                        userpwd VARCHAR(256) NOT NULL,
                        isonline INTEGER DEFAULT 1
                    );""")
        self.databaseServer.commit()
        curs.close()
        
        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()
        print(f"Listening on {(self.HOST, self.PORT)}")

    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request."""
        conn, addr = self.sock.accept()  # Should be ready to read
        msg = conn.recv(1024).decode()
        user_credentials: dict = json.loads(msg)
        username = user_credentials['Username']
        password = user_credentials['Password']
        newuser = user_credentials['Newuser']
          
        # TODO :- this block needs to be changed 
        if newuser:
            if username in users.keys():
                conn.sendall("invalid".encode())
                # conn.close()
                print("yes1")
                return
            else:
                users[username] = password # add user.
        elif (username not in users.keys() or password != users[username]):
            conn.sendall("invalid".encode())
            # conn.close()
            print("yes2")
            return

        print("Accepted connection from " + RED + str(addr) + RESET + " with username "  + GREEN + username + RESET)
        
        curs = self.databaseServer.cursor()
        curs.execute("INSERT INTO \"usercreds\" (username, userpwd) VALUES (%s,%s)",(username,password))
        curs.close()
        
        onlineUserSockets[username] = conn # change to bool = True
        conn.sendall('valid'.encode())
        conn.setblocking(False)
        data = SimpleNamespace(username=username, addr=addr, inb=b"", outb=b"")
        events = EVENT_READ | EVENT_WRITE
        self.selector.register(conn, events, data=data)

    def serve_client(self, key: SelectorKey, mask: bool):
        """
        Main serve loop, monitors client connections.
        """
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
                    print("Closing connection from address " + RED + str(data.addr) + RESET + ", username " + GREEN + data.username + RESET)
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
            print(f"Client " + GREEN + data.username + RESET + " closed the connection.")
            return

    def run(self):
        # lsock.setblocking(False)
        self.selector.register(fileobj=self.sock, events=EVENT_READ, data=None)

        try:
            while True:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept_client()
                    else:
                        self.serve_client(key, mask)
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
        self.selector.close()

server = Server()
server.run()


