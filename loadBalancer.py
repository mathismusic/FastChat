import socket
import json
import sys
import ast
import psycopg2
from server import Server
from globals import Globals
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE, SelectorKey
from message import *

# load balancer server
class LoadBalancer:
    def __init__(self, servers: list[list[str]], host: str, port: str, database: str, algorithm='least-load') -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.HOST = host  # The load balancer's hostname or IP address
        self.PORT = int(port)  # The port used by the balancer
        self.servers = list(servers)
        self.userDBName = database
        self.algorithm = algorithm
        self.selector = DefaultSelector()
        self.handler = None;
        self.databaseServer = psycopg2.connect(
            database=self.userDBName,
            host=self.HOST,
            user="postgres",
            password="password",
            port="5432"
        )
        print("load balancer host: " + self.HOST)
        self.sock.bind((self.HOST, self.PORT))
        self.sock.listen()
        print(f"Listening on {(self.HOST, self.PORT)}")
    
    # the load balancer does the work of accepting clients when they try to login
    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request. The accepted client is connected to a chosen server"""
        
        conn, addr = self.sock.accept()  # Should be ready to read
        self.handler = ServerMessageHandler(conn, addr)

        msg = self.handler.read()
        print(msg)
        user_credentials = msg

        username = user_credentials['Username']
        password = user_credentials['Password']
        user_priv_key = user_credentials['Private_Key']
        user_pub_key = user_credentials['Public_Key']
        newuser = user_credentials['Newuser']
        
        self.handler.connectedTo=username

        curs = self.databaseServer.cursor()
        curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
        data = curs.fetchall()
        if newuser:
            if len(data) > 0:
                self.handler.write("invalid")
                print("yes1")
                return
            else:
                curs.execute("INSERT INTO \"usercreds\" (username,userpwd,userprivkey, userpubkey) VALUES (%s, %s, %s, %s)",(username,password, user_priv_key, user_pub_key)) # add user.
                self.databaseServer.commit()
        elif (len(data) == 0 or password != data[0][2]):
            # print(data[0][2])
            self.handler.write("invalid")
            # conn.close()
            print("yes2")
            return

        # connect the user to server
        server = self.choose_server()
        self.handler.write({"hostname": server[0], "port": server[1]})
        # conn.sendall(json.dumps({"hostname": server[0], "port": server[1]}).encode())
        curs.execute("UPDATE \"usercreds\" SET connectedto=%s WHERE username=%s",(self.servers.index(server),username))
        self.databaseServer.commit()
        curs.close()
        return
        # server.accept_client(conn, addr, username, password)

    def choose_server(self) -> list[str]:
        ans = 0
        for i in range(self.servers):
            if Globals.Servers[i][2] < ans:
                ans = i
        return Globals.Servers[i]
        return self.servers[0]
    
    def run(self):
        # lsock.setblocking(False)
        self.selector.register(fileobj=self.sock, events=EVENT_READ, data=None)

        try:
            while True:
                events = self.selector.select(timeout=None)
                for key, mask in events:
                    if key.data is None:
                        self.accept_client()
                        
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
        self.selector.close()

if __name__ == "__main__":
    # lb = LoadBalancer(json.loads(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    args = str([[[Globals.default_host, "61001", "fastchat_users"], [Globals.default_host, "61002", "fastchat_users"], [Globals.default_host, "61003", "fastchat_users"], [Globals.default_host, "61004", "fastchat_users"], [Globals.default_host, "61005", "fastchat_users"]], Globals.default_host, "61051", "fastchat_users", "least-load"])
    # args = input()
    # print("||" + repr(args))
    # print(ast.literal_eval(args))
    lb = LoadBalancer(*ast.literal_eval(args))
    lb.run()