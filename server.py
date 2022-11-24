import sys
import socket
import selectors
from types import SimpleNamespace
import json
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from color_codes import *
from globals import Globals
from message import *

# 192.168.103.215

#users = {}
class Server:
    """Server class. Contains host address and port, 
    along with a connection to the PSQL server hosted locally."""
    def __init__(self, host: str, port: str, database: str, index: str) -> None:
        """Constructor, initializes to a default IP and port. Creates empty databases."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = host  # The server's hostname or IP address
        self.PORT = int(port)  # The port used by the server
        self.index = index
        self.numClients = 0
        self.selector = selectors.DefaultSelector()
        self.userDBName = database
        self.onlineUserSockets: dict[str, ServerMessageHandler] = {}
        self.serverConnections=[None]*len(Globals.Servers)

        # self.databaseServer = psycopg2.connect(
        #     host=self.HOST,
        #     user="postgres",
        #     password="password",
        #     port="5432"
        # )
        # self.databaseServer.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        # curs = self.databaseServer.cursor()
        # #curs.execute("DROP DATABASE IF EXISTS " + self.userDBName)
        # #curs.execute("CREATE DATABASE IF NOT EXISTS " + self.userDBName)
        
        # self.databaseServer.commit()
        # curs.close()
        # self.databaseServer.close()

        self.databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )


        # curs = self.databaseServer.cursor()
        # curs.execute("""CREATE TABLE IF NOT EXISTS usercreds (
        #                 userid SERIAL PRIMARY KEY,
        #                 username VARCHAR(256) NOT NULL UNIQUE,
        #                 userpwd VARCHAR(256) NOT NULL
        #             );""")
        # self.databaseServer.commit()
        # curs.execute("""CREATE TABLE IF NOT EXISTS pending (
        #                 msgid SERIAL NOT NULL PRIMARY KEY,
        #                 sender VARCHAR(256) NOT NULL,
        #                 receiver VARCHAR(256) NOT NULL,
        #                 jsonmsg TEXT NOT NULL,
        #                 sendtime TIMESTAMP NOT NULL
        #             );""")
        # curs.execute("ALTER TABLE pending ALTER COLUMN sendtime SET DEFAULT now();")
        # self.databaseServer.commit()
        # curs.close()
        # # isonline INTEGER DEFAULT 1
        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()
        print(f"Server #{self.index} is operational!")
        print(f"Listening on {(self.HOST, self.PORT)}")

    def accept_connection(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request."""
        conn, addr = self.sock.accept()  # Should be ready to read
        
        s = ServerMessageHandler(conn, addr)
        
        msg = s.read()
        # msg = conn.recv(1024).decode()
        
        if msg[:7]=="Server ":
            s.connectedTo = msg
            # serverindex = int(msg[7:])
            self.onlineUserSockets[msg] = s
            conn.setblocking(False)
            data = SimpleNamespace(username=msg)
            events = EVENT_READ | EVENT_WRITE
            self.selector.register(conn,events,data=data)
            return
            
        
        user_credentials: dict = json.loads(msg)
        username = user_credentials['Username']
#     password = user_credentials['Password']
#     newuser = user_credentials['Newuser']
        
#     # TODO :- this block needs to be changed
        curs = self.databaseServer.cursor()
#     curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
#     data = curs.fetchall()
#     if newuser:
#         if len(data)!=0:
#             conn.sendall("invalid".encode())
#             print("yes1")
#             return
#         else:
#             print("yes3")
#             curs.execute("INSERT INTO \"usercreds\" (username,userpwd) VALUES (%s, %s)",(username,password)) # add user.
#             self.databaseServer.commit()
#     elif (len(data)==0 or password != data[0][2]):
#         conn.sendall("invalid".encode())
#         # conn.close()
#         print("yes2")
#         return


        print("Accepted connection from " + RED + str(addr) + RESET + " with username "  + GREEN + username + RESET)
        self.numClients += 1
    
#     # curs = self.databaseServer.cursor()
#     # curs.execute("INSERT INTO \"usercreds\" (username, userpwd) VALUES (%s,%s)",(username,password))
#     # curs.close()
    
        self.onlineUserSockets[username] = s # change to bool = True
#     conn.sendall('valid'.encode())
    
        conn.setblocking(False)
        curs.execute("SELECT msgid,jsonmsg,sendtime FROM pending WHERE receiver=%s ORDER BY sendtime",(username,))
    
        messages = curs.fetchall()
        self.onlineUserSockets[username].requests.addrequest(messages)
        
        # self.onlineUserSockets[username].sendall(json.dumps(messages,default=str).encode())
        # self.onlineUserSockets[username].sendall(str(len(messages)).encode())
        self.onlineUserSockets[username].write(str(len(messages)))
        for mess in messages:
            # self.onlineUserSockets[username].sendall(json.dumps(mess[3]).encode())
            curs.execute("DELETE FROM pending WHERE msgid=%s",(mess[0],))
            self.onlineUserSockets[username].write(mess)
            self.databaseServer.commit()
        curs.close()
        data = SimpleNamespace(username=username, addr=addr)
        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        self.selector.register(conn, events, data=data)

    # def accept_connection(self, conn: socket.socket, addr, username: str, password: str):
    #     print("Accepted connection from " + RED + str(addr) + RESET + " with username "  + GREEN + username + RESET)
    #     self.numClients += 1
        
    #     self.onlineUserSockets[username] = conn # change to bool = True
    #     conn.sendall('valid'.encode())
        
    #     curs = self.databaseServer.cursor()
    #     curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
    #     conn.setblocking(False)
    #     curs.execute("SELECT msgid,jsonmsg,sendtime FROM pending WHERE receiver=%s ORDER BY sendtime",(username,))
        
    #     messages = curs.fetchall()
    #     self.onlineUserSockets[username].sendall(json.dumps(messages,default=str).encode())
    #     # self.onlineUserSockets[username].sendall(str(len(messages)).encode())
    #     for mess in messages:
    #         # self.onlineUserSockets[username].sendall(json.dumps(mess[3]).encode())
    #         curs.execute("DELETE FROM pending WHERE msgid=%s",(mess[0],))
    #         self.databaseServer.commit()
    #     curs.close()
    #     data = SimpleNamespace(username=username, addr=addr, inb=b"", outb=b"")
    #     events = EVENT_READ | EVENT_WRITE
    #     self.selector.register(conn, events, data=data)
    def serve_client(self, key: selectors.SelectorKey, mask: bool):
        """
        Main serve loop, monitors client connections.
        """
        sock: socket.socket = key.fileobj
        data: SimpleNamespace = key.data
        username = data.username
        try:
            if mask & EVENT_READ:
                msg_str = self.onlineUserSockets[username].read()
                # recv_data = sock.recv(1024)  # Should be ready to read
                if msg_str:
                    # data.outb += recv_data
                    msg = json.loads(msg_str)
                    curs = self.databaseServer.cursor()
                    curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(msg['Recipient'],))
                    userentry = curs.fetchall()
                    if len(userentry)==0:
                        self.onlineUserSockets[username].write("invalid_recipient")
                        # sock.sendall('invalid_recipient'.encode())
                        return
                    elif msg['Recipient'] not in self.onlineUserSockets:
                        if userentry[0][5]==-1:
                            curs.execute("INSERT INTO pending (sender,receiver,jsonmsg) VALUES (%s,%s,%s) ",(msg['Sender'],msg['Recipient'],msg_str))
                            self.databaseServer.commit()
                        else:
                            self.onlineUserSockets["Server " + str(userentry[0][5])].write(msg_str)
                            # self.serverConnections[userentry[0][5]].sendall(recv_data)
                            
                    else: # user is online and in the same server
                        self.onlineUserSockets[msg['Recipient']].write(msg_str)
                        # self.onlineUserSockets[msg['Recipient']].sendall(recv_data)
                    
                    curs.close()
                    # give acknowledgement of received to the sender
                    if username[7:] != 'Server ': 
                        self.onlineUserSockets[username].write("received")
                    # print(f"Client {data.username} to {msg['Recipient']}:", msg['Message'])
                
                # else the read returned nothing - the client did not try to send anything
                else:
                    print("Closing connection from address " + RED + str(data.addr) + RESET + ", username " + GREEN + username + RESET)
                    self.selector.unregister(sock)
                    if username[:7]=="Server ":
                        self.serverConnections[int(username[7:])]=None
                    else:
                        self.numClients -= 1
                        self.onlineUserSockets.pop(username)
                    sock.close()
            # if mask & EVENT_WRITE:
            #     if data.outb:
            #         response = "received"
            #         data.outb = response.encode()
            #         # print(f"Echoing {data.outb!r} to {data.addr}")
            #         sent = sock.send(data.outb)  # Should be ready to write
            #         data.outb = data.outb[sent:]
        except BrokenPipeError:
            print(f"Client " + GREEN + username + RESET + " closed the connection.")
            return

    def run(self):
        # lsock.setblocking(False)
        self.selector.register(fileobj=self.sock, events=selectors.EVENT_READ, data=None)

        try:
            while True:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept_connection()
                    else:
                        self.serve_client(key, mask)
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
        self.selector.close()
        
    def makeKn(self):
        for i in range(0,int(self.index)):
            self.serverConnections[i] = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.serverConnections[i].connect((Globals.Servers[i][0],int(Globals.Servers[i][1])))
            s = "Server " + self.index
            self.serverConnections[i].sendall(s.encode())
            data = SimpleNamespace(username=s, addr=(Globals.Servers[i][0],int(Globals.Servers[i][1])))
            events = selectors.EVENT_READ | selectors.EVENT_WRITE
            self.selector.register(self.serverConnections[i],events,data=data)

    def num_active_clients(self):
        return self.numClients

if __name__ == '__main__':
    server = Server(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
    server.makeKn()
    server.run()


