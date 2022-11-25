import socket
import json
import sys
import ast
import psycopg2
from server import Server
import globals
import importlib
importlib.reload(globals)
import selectors
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
        self.selector = selectors.DefaultSelector()
        self.handler = None
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
        self.sock.setblocking(True)
        self.se = 0
    
    # the load balancer does the work of accepting clients when they try to login
    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request. The accepted client is connected to a chosen server"""
        
        conn, addr = self.sock.accept()  # Should be ready to read
        conn.setblocking(True)
        self.handler = ServerMessageHandler(conn, addr)
        # print('0')
        msg = self.handler.read()
        print(type(msg))
        if type(msg) == str: print("|" + msg + "|", msg is None, msg == "")
        user_credentials = msg # why we sending to lsock
        # print('a')
        username = user_credentials['Username']
        # print('b')
        password = user_credentials['Password']
        # print('c')
        user_priv_key = user_credentials['Private_Key']
        # print('d')
        user_pub_key = user_credentials['Public_Key']
        # print('e')
        newuser = user_credentials['Newuser']
        
        self.handler.connectedTo=username

        curs = self.databaseServer.cursor()
        # print('f')
        curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
        # print('g')
        data = curs.fetchall()
        # print('h')
        if newuser:
            if len(data) > 0:
                # print('i')
                self.handler.write("invalid")
                # print('j')
                # print("yes1")
                return
            else:
                # print('k')
                curs.execute("INSERT INTO \"usercreds\" (username,userpwd,userprivkey, userpubkey) VALUES (%s, %s, %s, %s)",(username,password, user_priv_key, user_pub_key)) # add user.
                self.databaseServer.commit()
                # print('l')
        elif (len(data) == 0 or password != data[0][2]):
            # print(data[0][2])
            # print('m')
            self.handler.write("invalid")
            # print('n')
            # conn.close()
            # print("yes2")
            return

        # connect the user to server
        # print('o')
        server = self.choose_server()
        # print('p')
        self.handler.write({"hostname": server[0], "port": server[1]})
        # print('q')
        # conn.sendall(json.dumps({"hostname": server[0], "port": server[1]}).encode())
        curs.execute("UPDATE \"usercreds\" SET connectedto=%s WHERE username=%s",(self.servers.index(server),username))
        self.databaseServer.commit()
        curs.close()
        # print('r')
        conn.close()
        return
        # server.accept_client(conn, addr, username, password)

    def choose_server(self) -> list[str]:
        self.se = (self.se + 1) % len(globals.Globals.Servers)
        return [globals.Globals.Servers[self.se][0], globals.Globals.Servers[self.se][1]]
        ans = 0
        print(globals.Globals.Servers)
        for i in range(len(globals.Globals.Servers)):
            if globals.Globals.Servers[i][2] < globals.Globals.Servers[ans][2]:
                ans = i
        return [globals.Globals.Servers[ans][0], globals.Globals.Servers[ans][1]]
        return self.servers[0]
    
    def run(self):
        # print('s')
        self.selector.register(fileobj=self.sock, events=selectors.EVENT_READ, data=None)
        # print('t')
        try:
            while True:
                events = self.selector.select(timeout=None)
                # print(events)
                # print('x')
                for key, mask in events:
                    print(key.data is None, mask)
                    self.accept_client()
                        
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
        self.selector.close()

if __name__ == "__main__":
    # lb = LoadBalancer(json.loads(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    args = str([[[globals.Globals.default_host, "61001"], [globals.Globals.default_host, "61002"], [globals.Globals.default_host, "61003"], [globals.Globals.default_host, "61004"], [globals.Globals.default_host, "61005"]], globals.Globals.default_host, "61051", "fastchat_users", "least-load"])
    # args = input()
    # print("||" + repr(args))
    # print(ast.literal_eval(args))
    lb = LoadBalancer(*ast.literal_eval(args))
    lb.run()