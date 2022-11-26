import socket
import select
import ast
import psycopg2
import globals
from message import *
import random
# import json
# import sys

# load balancer server
class LoadBalancer:
    """The Load Balancer is a special type of Server, which handles authentication, account creation,
    and server load balancing. It implements a round robin distribution of the client load. An
    alternate algorithm based on least-load identification can be given as a flag."""
    def __init__(self, servers: list[list[str]], host: str, port: str, database: str, algorithm='least-load') -> None:
        """
        Constructor
        
        :param: servers: Contains the addresses of each of the main servers as a list
        :type: servers: list[list[int]]
        :param: host: hostname
        :param: port: port number
        :param: database: Databse name
        :param: algorithm: The load balancing method
        :type: algorithm: str
        """
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        self.HOST = host  # The load balancer's hostname or IP address
        self.PORT = int(port)  # The port used by the balancer
        self.servers = list(servers)
        self.userDBName = database
        self.algorithm = algorithm
        self.events = []
        self.handlers = {}
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
        self.se = -1
    
    # the load balancer does the work of accepting clients when they try to login
    def accept_client(self):
        """Accepts the connection request from a client, after correct authentication.
        Creates a new account on corresponding request.
        The accepted client is connected to a chosen server, and any pending messages since the
        client's last session are sent"""
        
        conn, addr = self.sock.accept()  # Should be ready to read
        conn.setblocking(True)
        self.events.append(conn)
        self.handlers[addr] = MessageHandler(conn, addr)
        
    def check_and_allocate_client(self, conn: socket.socket):
        """
        Authorizes user by requesting credentials and verifying them. If not verified, it sends "invalid" back to the client. Otherwise, it appropriately chooses a server for the client and sends the host and port of this server back to the client.

        :param: conn: the socket object at the load balancer that has connected to the client
        :type: socket.socket
        """
        curr_handler = self.handlers[conn.getpeername()]
        msg = curr_handler.read()
        if msg is None:
            self.events.remove(conn)
            self.handlers.pop(conn.getpeername())
            print("Connection lost.")
            return
        # print(type(msg))
        # if type(msg) == str: print("|" + msg + "|", msg is None, msg == "")
        user_credentials = msg
        username = user_credentials['Username']
        password = user_credentials['Password']
        user_priv_key = user_credentials['Private_Key']
        user_pub_key = user_credentials['Public_Key']
        newuser = user_credentials['Newuser']
        
        curr_handler.connectedTo = username

        curs = self.databaseServer.cursor()
        curs.execute("SELECT * FROM \"usercreds\" WHERE username=%s",(username,))
        data = curs.fetchall()
        if newuser:
            if len(data) > 0:
                curr_handler.write("invalid")
                return
            else:
                curs.execute("INSERT INTO \"usercreds\" (username,userpwd,userprivkey, userpubkey) VALUES (%s, %s, %s, %s)",(username,password, user_priv_key, user_pub_key)) # add user.
                self.databaseServer.commit()
        elif (len(data) == 0 or password != data[0][2]):
            # print(data[0][2])
            curr_handler.write("invalid")
            return

        # connect the user to server
        server = self.choose_server()
        curr_handler.write({"hostname": server[0], "port": server[1]})
        curs.execute("UPDATE \"usercreds\" SET connectedto=%s WHERE username=%s",(self.servers.index(server),username))
        self.databaseServer.commit()
        curs.close()
        # conn.close()
        self.events.remove(conn)
        self.handlers.pop(conn.getpeername())
        conn.close()
        return

    def choose_server(self) -> list[str]:
        """
        Decides which server to send the client to using self.algorithm.

        :return: the host and port of the server chosen, as a list.
        :rtype: list[str]
        """
        if self.algorithm == 'round-robin':
            self.se = (self.se + 1) % len(globals.Globals.Servers)
            return [globals.Globals.Servers[self.se][0], globals.Globals.Servers[self.se][1]]
        if self.algorithm == 'least-load':
            curs = self.databaseServer.cursor()
            curs.execute("""
            SELECT 
                serverindex
            FROM 
                serverload 
            WHERE 
                numclients=(SELECT MIN(numclients) FROM serverload)
            """)
            res = curs.fetchall()[0][0]
            curs.close()
            return [globals.Globals.Servers[res][0], globals.Globals.Servers[res][1]]
        if self.algorithm == 'naive':
            return self.servers[random.randint(0, len(globals.Globals.Servers) - 1)]
        raise Exception('Invalid algorithm')
        
    
    def run(self):
        """
        Main callback to accept and allot servers to clients.
        """
        # print('s')
        self.events.append(self.sock)
        # print('t')
        try:
            while True:
                readable_events, _, _ = select.select(self.events,[],[])
                for readable_event in readable_events:
                    if readable_event == self.sock:
                        self.accept_client()
                    else:
                        self.check_and_allocate_client(readable_event)         
        except KeyboardInterrupt:
            print("Caught keyboard interrupt, exiting")
        
if __name__ == "__main__":
    # lb = LoadBalancer(json.loads(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])

    args = str([[[globals.Globals.default_host, "61001"], [globals.Globals.default_host, "61002"], [globals.Globals.default_host, "61003"], [globals.Globals.default_host, "61004"], [globals.Globals.default_host, "61005"]], globals.Globals.default_host, "61051", "fastchat_users", "least-load"])
    lb = LoadBalancer(*ast.literal_eval(args))
    lb.run()